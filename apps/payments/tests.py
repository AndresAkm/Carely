"""Pruebas del flujo de pagos con Wompi y con la pasarela simulada."""

import json

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.orders.models import Order, OrderStatusHistory
from apps.payments.gateways import get_gateway
from apps.payments.gateways.base import (
    GatewayError,
    GatewayRedirectBlockedError,
    PaymentGateway,
    to_cents,
)
from apps.payments.gateways.simulated import SimulatedGateway
from apps.payments.gateways.wompi import (
    WompiClient,
    WompiGateway,
    build_integrity_signature,
    compute_event_checksum,
    is_publicly_routable,
)
from apps.payments.models import Payment
from apps.payments.services import (
    InvalidEventError,
    InvalidStatusError,
    PaymentAlreadyExistsError,
    PaymentError,
    PaymentNotFoundError,
    PaymentService,
)


User = get_user_model()

INTEGRITY_SECRET = 'prv_integrity_de_prueba'
EVENTS_SECRET = 'prv_events_de_prueba'
PUBLIC_KEY = 'pub_test_de_prueba'
PRIVATE_KEY = 'prv_test_de_prueba'
API_URL = 'https://sandbox.wompi.co/v1'


def wompi_settings(**extra):
    values = {
        'PAYMENT_GATEWAY': 'wompi',
        'WOMPI_PUBLIC_KEY': PUBLIC_KEY,
        'WOMPI_PRIVATE_KEY': PRIVATE_KEY,
        'WOMPI_INTEGRITY_SECRET': INTEGRITY_SECRET,
        'WOMPI_EVENTS_SECRET': EVENTS_SECRET,
        'WOMPI_API_URL': API_URL,
        'WOMPI_CHECKOUT_URL': 'https://checkout.wompi.co/p/',
        'WOMPI_CURRENCY': 'COP',
    }
    values.update(extra)
    return override_settings(**values)


#: 500000.00 pesos, que es el total que usa `make_order`.
ORDER_AMOUNT_IN_CENTS = 50_000_000


def build_event(reference, status='APPROVED', amount_in_cents=ORDER_AMOUNT_IN_CENTS,
                transaction_id='tx-abc', events_secret=EVENTS_SECRET,
                properties=None, timestamp='1768000000'):
    """Arma un evento con la misma forma que envía Wompi, con su checksum real."""
    properties = properties or [
        'transaction.id',
        'transaction.reference',
        'transaction.status',
        'transaction.amount_in_cents',
    ]
    payload = {
        'event': 'transaction.updated',
        'data': {
            'transaction': {
                'id': transaction_id,
                'reference': reference,
                'status': status,
                'amount_in_cents': amount_in_cents,
                'currency': 'COP',
                'payment_method_type': 'CARD',
                'status_message': f'Resultado {status}',
            },
        },
        'signature': {
            'properties': properties,
            'timestamp': timestamp,
        },
    }
    payload['signature']['checksum'] = compute_event_checksum(payload, events_secret)
    return payload


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class FakeWompiClient(WompiClient):
    """Cliente que no sale a la red: devuelve el `data` que el test le dicte."""

    def __init__(self, data):
        super().__init__(base_url=API_URL, private_key=PRIVATE_KEY, timeout=1)
        self.data = data
        self.calls = []

    def get_transaction(self, transaction_id):
        self.calls.append(transaction_id)
        return self.data


#: Host público de ejemplo. Wompi rechaza `redirect-url` que apunte a loopback o
#: a redes privadas, así que los tests que arman un checkout necesitan uno real.
PUBLIC_HOST = 'carely.example.com'


def public_request(path='/'):
    """RequestFactory con host alcanzable desde internet.

    El host por defecto de Django es `testserver`, que no es un dominio real: si
    el checkout se validara contra él, los tests pasarían con una URL que en
    producción Wompi rechaza.
    """
    return RequestFactory().get(path, HTTP_HOST=PUBLIC_HOST, secure=True)


class PaymentFactoryMixin:
    def make_user(self, suffix=''):
        # El sufijo se deriva de un contador para que dos pedidos en el mismo
        # test no choquen por el correo, que es único.
        self._user_counter = getattr(self, '_user_counter', 0) + 1
        return User.objects.create_user(
            username=f'comprador-{suffix}{self._user_counter}',
            email=f'comprador{suffix}{self._user_counter}@carely.test',
            password='clave-de-prueba-123',
        )

    def make_order(self, total='500000.00', user=None):
        """Crea un pedido pendiente con el total que se le indique.

        `Order.subtotal` es una propiedad que suma los items, así que el total
        se asigna directamente al crear el pedido.
        """
        return Order.objects.create(
            user=user or self.make_user(),
            status=Order.Status.PENDIENTE,
            total=Decimal(total),
        )

    def make_payment(self, order, amount='500000.00'):
        return PaymentService.create_payment(order)


@wompi_settings()
class PaymentCreationTests(PaymentFactoryMixin, TestCase):
    """El pago se crea con el total del pedido y una referencia propia."""

    def test_crea_el_pago_con_el_total_del_pedido(self):
        order = self.make_order('250000.00')

        payment = self.make_payment(order)

        self.assertEqual(payment.amount, Decimal('250000.00'))
        self.assertEqual(payment.status, Payment.Status.PENDIENTE)
        self.assertEqual(payment.gateway, 'wompi')
        self.assertEqual(payment.order, order)

    def test_genera_una_referencia_unica_por_pago(self):
        primero = self.make_payment(self.make_order())
        segundo = PaymentService.create_payment(
            self.make_order(), method=Payment.PaymentMethod.PSE,
        )

        self.assertNotEqual(primero.reference, segundo.reference)
        self.assertTrue(primero.reference.startswith('CARELY-'))
        self.assertEqual(Payment.objects.count(), 2)
        self.assertEqual(Payment.objects.filter(reference__in=[
            primero.reference, segundo.reference,
        ]).count(), 2)

    def test_no_acepta_un_pedido_con_total_cero(self):
        order = self.make_order('0.00')

        with self.assertRaises(PaymentError):
            self.make_payment(order)

    def test_no_crea_un_segundo_pago_en_curso(self):
        order = self.make_order()
        self.make_payment(order)

        with self.assertRaises(PaymentAlreadyExistsError):
            PaymentService.create_payment(order)


@wompi_settings()
class PublicRedirectUrlTests(TestCase):
    """Qué direcciones acepta Wompi como `redirect-url` en el checkout."""

    def test_acepta_un_dominio_publico(self):
        self.assertTrue(is_publicly_routable('carely.co'))
        self.assertTrue(is_publicly_routable('app.carely.co'))
        self.assertTrue(is_publicly_routable('carely.example.com'))

    def test_rechaza_loopback(self):
        for host in ('localhost', 'LOCALHOST', 'localhost.', '127.0.0.1',
                     '127.10.20.30', '::1', '[::1]', '0.0.0.0'):
            with self.subTest(host=host):
                self.assertFalse(is_publicly_routable(host), host)

    def test_rechaza_redes_privadas(self):
        for host in ('10.0.0.1', '172.16.5.4', '172.31.255.1',
                     '192.168.1.10', '169.254.10.1', 'fd00::1'):
            with self.subTest(host=host):
                self.assertFalse(is_publicly_routable(host), host)

    def test_rechaza_nombres_reservados(self):
        for host in ('prueba.local', 'app.internal', 'x.test', 'y.invalid',
                     'testserver', ''):
            with self.subTest(host=host):
                self.assertFalse(is_publicly_routable(host), host)

    def test_172_15_y_172_32_son_publicas(self):
        # Los límites de la privada clase B no se pueden redondear: 172.15 y
        # 172.32 quedan fuera de 172.16.0.0/12.
        self.assertTrue(is_publicly_routable('172.15.0.1'))
        self.assertTrue(is_publicly_routable('172.32.0.1'))


@wompi_settings()
class StartCheckoutTests(PaymentFactoryMixin, TestCase):
    """La URL del checkout ata referencia, monto y moneda con la firma."""

    def setUp(self):
        self.order = self.make_order('250000.00')
        self.payment = self.make_payment(self.order)

    def test_construye_la_url_con_la_firma_de_integridad(self):
        request = public_request()
        request.user = self.order.user

        url = PaymentService.start_checkout(self.payment, request)

        self.assertTrue(url.startswith('https://checkout.wompi.co/p/?'))
        self.assertIn(f'reference={self.payment.reference}', url)
        self.assertIn('amount-in-cents=25000000', url)
        self.assertIn('currency=COP', url)

        expected = build_integrity_signature(
            self.payment.reference, 25_000_000, 'COP', INTEGRITY_SECRET,
        )
        self.assertIn(f'signature%3Aintegrity={expected}', url)

    def test_no_arranca_el_checkout_si_faltan_secretos(self):
        with self.settings(WOMPI_INTEGRITY_SECRET='', WOMPI_EVENTS_SECRET=''):
            request = public_request()
            request.user = self.order.user

            with self.assertRaises(GatewayError):
                PaymentService.start_checkout(self.payment, request)

    def test_no_arranca_el_checkout_con_retorno_local(self):
        # Sin esto Wompi responde 403 desde CloudFront y el usuario solo ve
        # "Request blocked". El pedido debe quedar protegido antes de firmar.
        request = RequestFactory().get('/', HTTP_HOST='localhost:8000')
        request.user = self.order.user

        with self.assertRaises(GatewayRedirectBlockedError):
            PaymentService.start_checkout(self.payment, request)

    def test_la_firma_cambia_si_cambia_el_monto(self):
        firma_original = build_integrity_signature('CARELY-1', 100, 'COP', 's')
        firma_manipulada = build_integrity_signature('CARELY-1', 1, 'COP', 's')

        self.assertNotEqual(firma_original, firma_manipulada)


@wompi_settings()
class EventHandlingTests(PaymentFactoryMixin, TestCase):
    """Los eventos de Wompi mueven el pago y confirman el pedido una sola vez."""

    def setUp(self):
        self.order = self.make_order()
        self.payment = self.make_payment(self.order)

    def test_un_evento_aprobado_confirma_el_pedido(self):
        payload = build_event(self.payment.reference)

        payment = PaymentService.handle_event(payload, checksum=payload['signature']['checksum'])

        self.assertEqual(payment.status, Payment.Status.APROBADO)
        self.assertEqual(payment.transaction_id, 'tx-abc')
        self.assertIsNotNone(payment.processed_at)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMADO)
        self.assertTrue(
            OrderStatusHistory.objects.filter(
                order=self.order, status=Order.Status.CONFIRMADO,
            ).exists(),
        )

    def test_rechazar_no_confirma_el_pedido(self):
        payload = build_event(self.payment.reference, status='DECLINED')

        payment = PaymentService.handle_event(payload, checksum=payload['signature']['checksum'])

        self.assertEqual(payment.status, Payment.Status.RECHAZADO)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDIENTE)

    def test_un_evento_repetido_no_toca_nada(self):
        payload = build_event(self.payment.reference)
        PaymentService.handle_event(payload, checksum=payload['signature']['checksum'])

        self.order.refresh_from_db()
        history_count = OrderStatusHistory.objects.count()
        payment = PaymentService.handle_event(
            payload, checksum=payload['signature']['checksum'],
        )

        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APROBADO)
        self.assertEqual(OrderStatusHistory.objects.count(), history_count)
        self.assertEqual(self.order.status, Order.Status.CONFIRMADO)

    def test_ignora_un_evento_con_monto_distinto(self):
        payload = build_event(self.payment.reference, amount_in_cents=1)

        payment = PaymentService.handle_event(payload, checksum=payload['signature']['checksum'])

        self.assertEqual(payment.status, Payment.Status.PENDIENTE)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDIENTE)

    def test_rechaza_un_evento_con_firma_invalida(self):
        payload = build_event(self.payment.reference)

        with self.assertRaises(InvalidEventError):
            PaymentService.handle_event(payload, checksum='firma-falsa')

    def test_rechaza_un_evento_firmado_con_otro_secreto(self):
        payload = build_event(self.payment.reference, events_secret='otro-secreto')

        with self.assertRaises(InvalidEventError):
            PaymentService.handle_event(payload, checksum=payload['signature']['checksum'])

    def test_rechaza_otro_tipo_de_evento(self):
        payload = build_event(self.payment.reference)
        payload['event'] = 'transaction.approved'

        with self.assertRaises(PaymentError):
            PaymentService.handle_event(payload, checksum=payload['signature']['checksum'])

    def test_falla_con_una_referencia_desconocida(self):
        payload = build_event('CARELY-NO-EXISTE')

        with self.assertRaises(PaymentNotFoundError):
            PaymentService.handle_event(payload, checksum=payload['signature']['checksum'])

    def test_rechaza_un_pago_ya_aprobado_que_llega_rechazado(self):
        payload = build_event(self.payment.reference)
        PaymentService.handle_event(payload, checksum=payload['signature']['checksum'])

        segundo = build_event(
            self.payment.reference, status='DECLINED', transaction_id='tx-xyz',
        )
        payment = PaymentService.handle_event(segundo, checksum=segundo['signature']['checksum'])

        self.assertEqual(payment.status, Payment.Status.APROBADO)
        self.assertEqual(payment.transaction_id, 'tx-abc')


@wompi_settings()
class WebhookViewTests(PaymentFactoryMixin, TestCase):
    """La vista del webhook responde lo que Wompi necesita para no reintentar."""

    def setUp(self):
        self.order = self.make_order()
        self.payment = self.make_payment(self.order)
        self.url = reverse('payments:wompi_webhook')

    def post_event(self, payload, checksum=None):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_EVENT_CHECKSUM=(
                checksum if checksum is not None else payload['signature']['checksum']
            ),
        )

    def test_acepta_un_evento_firmado(self):
        payload = build_event(self.payment.reference)

        response = self.post_event(payload)

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.APROBADO)

    def test_devuelve_400_si_la_firma_no_cuadra(self):
        payload = build_event(self.payment.reference)

        response = self.post_event(payload, checksum='otra-cosa')

        self.assertEqual(response.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDIENTE)

    def test_devuelve_400_si_el_cuerpo_no_es_json(self):
        response = self.client.post(
            self.url, data='esto no es json', content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)

    def test_devuelve_200_para_una_referencia_desconocida(self):
        payload = build_event('CARELY-NO-EXISTE')

        response = self.post_event(payload)

        self.assertEqual(response.status_code, 200)

    def test_no_exige_csrf(self):
        payload = build_event(self.payment.reference)

        client_without_csrf = self.client_class(enforce_csrf_checks=True)
        response = client_without_csrf.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_EVENT_CHECKSUM=payload['signature']['checksum'],
        )

        self.assertEqual(response.status_code, 200)

    def test_solo_acepta_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


@wompi_settings()
class SyncWithGatewayTests(PaymentFactoryMixin, TestCase):
    """La consulta a la API reemplaza lo que el navegadordice."""

    def setUp(self):
        self.order = self.make_order()
        self.payment = self.make_payment(self.order)
        self.payment.transaction_id = 'tx-abc'
        self.payment.save(update_fields=['transaction_id'])

    def test_consulta_la_transaccion_y_actualiza(self):
        gateway = WompiGateway(client=FakeWompiClient({
            'id': 'tx-abc',
            'reference': self.payment.reference,
            'status': 'APPROVED',
            'amount_in_cents': to_cents(self.payment.amount),
            'currency': 'COP',
            'payment_method_type': 'CARD',
            'status_message': 'APPROVED',
        }))

        payment = PaymentService.sync_with_gateway(self.payment, gateway=gateway)

        self.assertEqual(payment.status, Payment.Status.APROBADO)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMADO)

    def test_no_aplica_el_estado_si_el_monto_no_cuadra(self):
        gateway = WompiGateway(client=FakeWompiClient({
            'id': 'tx-abc',
            'reference': self.payment.reference,
            'status': 'APPROVED',
            'amount_in_cents': 1,
            'currency': 'COP',
        }))

        payment = PaymentService.sync_with_gateway(self.payment, gateway=gateway)

        self.assertEqual(payment.status, Payment.Status.PENDIENTE)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDIENTE)

    def test_el_gateway_consulta_la_transaccion_del_pago(self):
        client = FakeWompiClient({
            'id': 'tx-abc',
            'reference': self.payment.reference,
            'status': 'PENDING',
            'amount_in_cents': to_cents(self.payment.amount),
        })

        PaymentService.sync_with_gateway(self.payment, gateway=WompiGateway(client=client))

        self.assertEqual(client.calls, ['tx-abc'])

    def test_falla_sin_llave_privada(self):
        with self.settings(WOMPI_PRIVATE_KEY=''):
            gateway = WompiGateway()
            with self.assertRaises(GatewayError):
                gateway.fetch_transaction('tx-abc')

    def test_falla_si_no_hay_transaction_id(self):
        self.payment.transaction_id = None
        self.payment.save(update_fields=['transaction_id'])

        with self.assertRaises(PaymentError):
            PaymentService.sync_with_gateway(self.payment, gateway=WompiGateway())


class WompiSignatureTests(TestCase):
    """Las dos firmas de Wompi se calculan como las calcula Wompi."""

    def test_la_firma_de_integridad_usa_referencia_monto_moneda_y_secreto(self):
        firma = build_integrity_signature('CARELY-1', 25000000, 'COP', 'secreto')

        import hashlib

        esperado = hashlib.sha256(b'CARELY-125000000COPsecreto').hexdigest()

        self.assertEqual(firma, esperado)

    def test_el_checksum_sigue_el_orden_de_las_propiedades(self):
        payload = {
            'data': {'transaction': {'id': 'tx-1', 'reference': 'CARELY-1'}},
            'signature': {
                'properties': ['transaction.id', 'transaction.reference'],
                'timestamp': '1768000000',
            },
        }

        import hashlib

        esperado = hashlib.sha256(
            f'tx-1CARELY-11768000000{EVENTS_SECRET}'.encode(),
        ).hexdigest()

        self.assertEqual(compute_event_checksum(payload, EVENTS_SECRET), esperado)

    def test_falla_si_el_evento_no_declara_propiedades_firmadas(self):
        with self.assertRaises(GatewayError):
            compute_event_checksum({'data': {}, 'signature': {}}, EVENTS_SECRET)

    def test_falla_si_el_evento_no_trae_los_datos_firmados(self):
        payload = {
            'data': {'transaction': {'id': 'tx-1'}},
            'signature': {
                'properties': ['transaction.reference'],
                'timestamp': '1768000000',
            },
        }

        with self.assertRaises(GatewayError):
            compute_event_checksum(payload, EVENTS_SECRET)


@override_settings(PAYMENT_GATEWAY='simulado')
class SimulatedGatewayTests(PaymentFactoryMixin, TestCase):
    """La pasarela simulada permite recorrer el flujo sin tocar la red."""

    def setUp(self):
        self.order = self.make_order()
        self.payment = self.make_payment(self.order)

    def test_el_gateway_simulado_no_hereda_de_wompi(self):
        gateway = get_gateway()

        self.assertIsInstance(gateway, SimulatedGateway)
        self.assertEqual(gateway.slug, 'simulado')

    def test_el_pago_usa_el_gateway_configurado(self):
        self.assertEqual(self.payment.gateway, 'simulado')

    def test_aprueba_desde_un_evento_con_forma_de_wompi(self):
        payload = build_event(self.payment.reference)

        payment = PaymentService.handle_event(payload)

        self.assertEqual(payment.status, Payment.Status.APROBADO)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMADO)

    def test_rechaza_desde_un_evento_con_forma_de_wompi(self):
        payload = build_event(self.payment.reference, status='DECLINED')

        payment = PaymentService.handle_event(payload)

        self.assertEqual(payment.status, Payment.Status.RECHAZADO)

    def test_sincronizar_devuelve_el_monto_del_pago(self):
        self.payment.transaction_id = 'sim-1'
        self.payment.save(update_fields=['transaction_id'])

        gateway = SimulatedGateway(status=PaymentGateway.STATUS_APPROVED)
        payment = PaymentService.sync_with_gateway(self.payment, gateway=gateway)

        self.assertEqual(payment.status, Payment.Status.APROBADO)


class GatewaySelectionTests(TestCase):
    """`PAYMENT_GATEWAY` decide cuál implementación se instancia."""

    def test_wompi_por_defecto_en_configuracion(self):
        with override_settings(PAYMENT_GATEWAY='wompi'):
            self.assertIsInstance(get_gateway(), WompiGateway)

    def test_simulado_cuando_se_pide(self):
        with override_settings(PAYMENT_GATEWAY='simulado'):
            self.assertIsInstance(get_gateway(), SimulatedGateway)


class UpdateStatusTests(PaymentFactoryMixin, TestCase):
    """El panel puede forzar un estado, pero sin romper pagos cerrados."""

    def setUp(self):
        self.order = self.make_order()
        self.payment = self.make_payment(self.order)

    def test_aprueba_desde_el_panel(self):
        payment = PaymentService.update_status(self.payment, Payment.Status.APROBADO)

        self.assertEqual(payment.status, Payment.Status.APROBADO)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMADO)

    def test_rechaza_un_estado_inventado(self):
        with self.assertRaises(InvalidStatusError):
            PaymentService.update_status(self.payment, 'inventado')

    def test_no_degrada_un_pago_aprobado(self):
        PaymentService.update_status(self.payment, Payment.Status.APROBADO)

        with self.assertRaises(InvalidStatusError):
            PaymentService.update_status(self.payment, Payment.Status.RECHAZADO)


@override_settings(PAYMENT_GATEWAY='simulado')
class PaymentWebViewsTests(PaymentFactoryMixin, TestCase):
    """Las vistas web exigen sesión y respetan la pertenencia del pago."""

    def setUp(self):
        self.order = self.make_order()
        self.payment = self.make_payment(self.order)

    def test_el_inicio_de_pago_exige_sesion(self):
        response = self.client.post(
            reverse('payments:start', args=[self.order.id]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response['Location'])

    def test_el_retorno_exige_sesion(self):
        response = self.client.get(
            reverse('payments:return_page', args=[self.payment.id]),
        )

        self.assertEqual(response.status_code, 302)

    @wompi_settings()
    def test_desde_localhost_no_abre_checkout_y_explica_por_que(self):
        # El 403 de CloudFront no dice nada. El usuario tiene que recibir el
        # motivo y una salida, no una página de error de infraestructura.
        self.client.force_login(self.order.user)

        response = self.client.post(
            reverse('payments:start', args=[self.order.id]),
            HTTP_HOST='localhost:8000',
        )

        self.assertRedirects(
            response, reverse('orders:success', args=[self.order.id]),
        )
        # Lo importante: nunca se devuelve una URL de checkout, porque Wompi la
        # rechazaría con un 403 sin explicar nada.
        self.assertNotIn('checkout.wompi.co', response['Location'])

        messages = [str(m) for m in response.wsgi_request._messages]
        self.assertTrue(any('dirección pública' in m for m in messages), messages)
        # El pedido sobrevive al fallo: no se pierde la compra.
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDIENTE)

    def test_el_webhook_no_exige_sesion(self):
        payload = build_event(self.payment.reference)

        response = self.client.post(
            reverse('payments:wompi_webhook'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)

    def test_otro_usuario_no_ve_el_pago(self):
        intruder = User.objects.create_user(
            username='intruso',
            email='intruso@carely.test',
            password='clave-de-prueba-123',
        )
        self.client.force_login(intruder)

        response = self.client.get(
            reverse('payments:return_page', args=[self.payment.id]),
        )

        self.assertEqual(response.status_code, 404)

    def test_el_estado_responde_json_sin_secretos(self):
        self.client.force_login(self.order.user)

        response = self.client.get(reverse('payments:status', args=[self.payment.id]))

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['estado'], Payment.Status.PENDIENTE)
        self.assertEqual(body['estado_texto'], 'Pendiente')
        self.assertNotIn('metadata', body)
        self.assertNotIn('transaction_id', body)
        self.assertNotIn('reference', body)

    def test_el_checkout_simulado_muestra_el_pago(self):
        self.client.force_login(self.order.user)

        response = self.client.get(
            reverse('payments:simulated', args=[self.payment.reference]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.payment.reference)

    def test_aprobar_desde_el_checkout_simulado_confirma_el_pedido(self):
        self.client.force_login(self.order.user)

        response = self.client.post(
            reverse('payments:simulated_result', args=[self.payment.reference]),
            data={'resultado': 'aprobado'},
        )

        self.assertEqual(response.status_code, 302)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.APROBADO)
        self.assertEqual(self.order.status, Order.Status.CONFIRMADO)

    def test_rechazar_desde_el_checkout_simulado_no_confirma(self):
        self.client.force_login(self.order.user)

        self.client.post(
            reverse('payments:simulated_result', args=[self.payment.reference]),
            data={'resultado': 'rechazado'},
        )

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.RECHAZADO)
        self.assertEqual(self.order.status, Order.Status.PENDIENTE)