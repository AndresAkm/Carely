from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.views.generic import TemplateView

from apps.catalog.models import Category, Product
from apps.core.permissions import is_admin
from apps.orders.models import Order

User = get_user_model()


class LandingView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['benefits'] = [
            {
                'icon': 'bi-shield-check',
                'title': 'Productos 100% Originales',
                'description': 'Trabajamos directamente con marcas reconocidas para garantizar la autenticidad de cada producto.',
            },
            {
                'icon': 'bi-truck',
                'title': 'Envío Rápido y Seguro',
                'description': 'Recibe tus productos en la puerta de tu casa con entregas rápidas y empaque cuidadoso.',
            },
            {
                'icon': 'bi-star',
                'title': 'Asesoría Personalizada',
                'description': 'Nuestro equipo de expertos te ayuda a encontrar los productos ideales para tu tipo de piel.',
            },
            {
                'icon': 'bi-arrow-repeat',
                'title': 'Devoluciones Sin Complicaciones',
                'description': 'Si no estás satisfecha, puedes devolver tu producto en un plazo de 30 días.',
            },
        ]
        context['why_us'] = [
            {
                'icon': 'bi-heart',
                'title': 'Cuidado de tu Piel',
                'description': 'Seleccionamos cuidadosamente cada producto para ofrecerte lo mejor para el cuidado de tu piel.',
            },
            {
                'icon': 'bi-emoji-smile',
                'title': 'Experiencia de Compra',
                'description': 'Disfruta de una experiencia de compra diseñada pensando en ti, desde la navegación hasta la entrega.',
            },
            {
                'icon': 'bi-award',
                'title': 'Compromiso con la Calidad',
                'description': 'Nos asociamos con marcas que comparten nuestro compromiso con la calidad y la sostenibilidad.',
            },
        ]
        context['categories'] = Category.objects.filter(is_active=True)
        context['featured_products'] = Product.objects.filter(
            is_active=True, featured=True
        ).select_related('category')[:6]
        return context


LEGAL_GROUPS = [
    {
        'id': 'terminos',
        'label': 'Términos y condiciones',
        'icon': 'bi-file-earmark-text',
        'sections': [
            {
                'title': 'Objeto y aceptación',
                'icon': 'bi-check2-circle',
                'paragraphs': [
                    'Estos Términos y Condiciones regulan el acceso y uso del sitio web de Carely, '
                    'mediante el cual se ofrecen productos de cuidado personal seleccionados y '
                    'comercializados bajo nuestras marcas. Versión vigente a partir del '
                    f'{settings.TERMS_EFFECTIVE_DATE}. Al registrarse, el usuario acepta de forma '
                    'libre, previa y consciente la totalidad de lo aquí establecido mediante la '
                    'casilla de aceptación del formulario de registro.',
                    'Si el usuario no está de acuerdo con alguna de las cláusulas, deberá '
                    'abstenerse de hacer uso de la plataforma. El uso posterior del sitio implica '
                    'la aceptación expresa de la versión vigente.',
                ],
            },
            {
                'title': 'Registro y cuenta de usuario',
                'icon': 'bi-person-badge',
                'paragraphs': [
                    'El acceso al área privada de Carely requiere la creación de una cuenta con '
                    'información veraz, completa y actualizada. El usuario es responsable de la '
                    'custodia de sus credenciales, incluida su contraseña, y de notificar de inmediato '
                    'cualquier uso no autorizado de su cuenta.',
                    'Podemos suspender, desactivar o cancelar cuentas cuando detectemos falsedad en los '
                    'datos, intentos de fraude, abuso del servicio o incumplimiento de estos términos. '
                    'La cuenta es personal e intransferible.',
                ],
            },
            {
                'title': 'Uso del servicio',
                'icon': 'bi-sliders',
                'paragraphs': [
                    'El usuario se compromete a utilizar la plataforma con fines lícitos y conforme a la '
                    'normativa colombiana, sin realizar acciones que puedan dañar la seguridad, la '
                    'integridad o la disponibilidad del servicio, ni interferir con el uso de otros '
                    'usuarios.',
                    'Queda prohibido intentar acceder a cuentas ajenas, realizar compras fraudulentas, '
                    'publicar contenido contrario a la ley o utilizar la información del sitio para '
                    'prácticas abusivas o discriminatorias.',
                ],
            },
            {
                'title': 'Productos, precios y disponibilidad',
                'icon': 'bi-bag-heart',
                'paragraphs': [
                    'Las fotografías de los productos son ilustrativas y pueden variar ligeramente del '
                    'artículo recibido. Las descripciones, contenidos e indicaciones se presentan '
                    'conforme a la información entregada por nuestros proveedores.',
                    'Los precios se expresan en pesos colombianos (COP) e incluyen los impuestos '
                    'aplicables, salvo que se indique lo contrario. Las ofertas, promociones y '
                    'descuentos tienen vigencia limitada y pueden modificarse o cancelarse sin previo '
                    'aviso.',
                ],
            },
            {
                'title': 'Pedidos y medios de pago',
                'icon': 'bi-credit-card',
                'paragraphs': [
                    'El pedido se entiende aceptado cuando Carely confirma la disponibilidad del '
                    'inventario y el pago. Podemos cancelar pedidos en casos de stock insuficiente, '
                    'precios incorrectos, sospechas de fraude o cualquier otra causa justificada que '
                    'será notificada al usuario.',
                    'Las transacciones se realizan a través de pasarelas de pago habilitadas por '
                    'Carely. Los datos de pago son procesados directamente por el proveedor y Carely '
                    'no almacena números de tarjeta ni claves de seguridad.',
                ],
            },
            {
                'title': 'Envíos y entregas',
                'icon': 'bi-truck',
                'paragraphs': [
                    'Los tiempos de entrega son estimaciones y dependen de la disponibilidad del '
                    'producto y de la transportadora. Los productos se despachan a la dirección '
                    'registrada por el usuario, quien debe verificar que los datos sean correctos.',
                    'Los retrasos o incidencias en la entrega serán gestionados directamente con la '
                    'transportadora. El usuario puede reportar anomalías desde su perfil dentro de los '
                    'plazos de garantía.',
                ],
            },
            {
                'title': 'Devoluciones, cambios y garantías',
                'icon': 'bi-arrow-repeat',
                'paragraphs': [
                    'Carely respeta la garantía legal de los productos de acuerdo con la normativa '
                    'colombiana (Ley 1489 de 2011, Ley 734 de 2002 y demás normas concordantes). Los '
                    'productos deben conservarse en su empaque original y sin uso para preservar la '
                    'garantía.',
                    'El usuario puede solicitar cambio o devolución por productos defectuosos o que no '
                    'correspondan a lo pedido, dentro del período de garantía y dentro de los treinta '
                    '(30) días calendario posteriores a la entrega.',
                ],
            },
            {
                'title': 'Propiedad intelectual',
                'icon': 'bi-copyright',
                'paragraphs': [
                    'Todos los contenidos del sitio —logotipos, marcas, textos, imágenes, videos y '
                    'código fuente— son propiedad de Carely o de sus licenciantes y se encuentran '
                    'protegidos por las normas de propiedad intelectual.',
                    'Queda prohibida la reproducción, adaptación, distribución o comunicación pública '
                    'de dichos contenidos sin autorización previa y por escrito, salvo los usos '
                    'permitidos por la ley con fines personales o de información.',
                ],
            },
            {
                'title': 'Limitación de responsabilidad',
                'icon': 'bi-exclamation-octagon',
                'paragraphs': [
                    'Carely procura ofrecer información veraz y actualizada sobre sus productos, pero '
                    'no garantiza que el contenido sea idéntico o exhaustivo en todos los casos. Los '
                    'resultados del uso de los productos varían de persona a persona y no '
                    'constituyen asesoría médica.',
                    'La responsabilidad de Carely se limita al valor de los productos o servicios '
                    'efectivamente reemplazados, salvo dolo, culpa grave o responsabilidad no '
                    'excluible conforme a la ley.',
                ],
            },
            {
                'title': 'Ley aplicable y soluciones',
                'icon': 'bi-bank',
                'paragraphs': [
                    'Estos términos se rigen por las leyes de la República de Colombia, en especial la '
                    'Ley 1581 de 2012 (protección de datos personales), la Ley 1712 de 2014, el '
                    'Estatuto del Consumidor y el Código de Comercio.',
                    'Las partes procurarán resolver cualquier controversia de forma amigable. Si no '
                    'fuere posible, las controversias serán sometidas a la jurisdicción de los jueces y '
                    'tribunales competentes de Medellín, Antioquia.',
                ],
            },
        ],
    },
    {
        'id': 'privacidad',
        'label': 'Política de privacidad',
        'icon': 'bi-shield-lock',
        'sections': [
            {
                'title': 'Responsable del tratamiento',
                'icon': 'bi-building',
                'paragraphs': [
                    f'{settings.SITE_NAME}, ubicada en {settings.CARELY_ADDRESS}, actúa como '
                    'responsable del tratamiento de los datos personales recogidos a través de '
                    f'este sitio web y es contactable en {settings.CARELY_EMAIL}.',
                ],
            },
            {
                'title': 'Datos que recopilamos',
                'icon': 'bi-fingerprint',
                'paragraphs': [
                    'Recopilamos los datos que usted nos entrega voluntariamente: nombre, apellidos, '
                    'correo electrónico, número de teléfono, direcciones de entrega e información de la '
                    'compra. Cuando navega por el sitio podemos registrar dirección IP, páginas '
                    'visitadas, navegador y dispositivo utilizados.',
                    'No solicitamos datos sensibles de carácter económico, social o biométrico a través '
                    'de este sitio. Cuando participan terceros (transportadoras y pasarelas de pago) '
                    'recibimos únicamente los datos estrictamente necesarios para prestar el servicio.',
                ],
            },
            {
                'title': 'Finalidad del tratamiento',
                'icon': 'bi-bullseye',
                'paragraphs': [
                    'Tratamos sus datos para gestionar su cuenta, procesar pedidos y pagos, coordinar '
                    'la entrega de los productos, enviar comunicaciones comerciales y transaccionales, '
                    'atender solicitudes, peticiones y quejas, cumplir obligaciones legales y prevenir '
                    'el fraude.',
                ],
            },
            {
                'title': 'Base legal y consentimiento',
                'icon': 'bi-patch-check',
                'paragraphs': [
                    'El tratamiento se realiza con base en su consentimiento previo, explícito, '
                    'informado y voluntario, y en el cumplimiento de las obligaciones legales y '
                    'convencionales derivadas de la relación comercial. Cuando actuamos con '
                    'consentimiento, puede retirarlo en cualquier momento escribiendo a '
                    f'{settings.CARELY_EMAIL}.',
                ],
            },
            {
                'title': 'Sus derechos',
                'icon': 'bi-person-check',
                'paragraphs': [
                    'Conforme al artículo 15 de la Ley 1581 de 2012 y a la Ley 1712 de 2014, puede '
                    'conocer, consultar, rectificar, actualizar, suprimir sus datos, revocar el '
                    'consentimiento y solicitar la revisión de las decisiones que puedan afectarlo, '
                    'así como presentar reclamo ante la Superintendencia de Industria y Comercio, '
                    'autoridad de protección de datos personales en Colombia.',
                ],
            },
            {
                'title': 'Uso de cookies y tecnologías similares',
                'icon': 'bi-cookie',
                'paragraphs': [
                    'Utilizamos cookies y tecnologías de rastreo para recordar sus preferencias, mantener '
                    'su sesión iniciada, entender el uso del sitio y mejorar nuestros contenidos y '
                    'sistemas de seguridad. La configuración de las cookies puede modificarse en su '
                    'navegador en cualquier momento.',
                    'Las cookies que utilizamos son propias y de terceros, y estas últimas se '
                    'encuentran sujetas a las políticas de privacidad de sus respectivos proveedores.',
                ],
            },
            {
                'title': 'Seguridad de la información',
                'icon': 'bi-lock',
                'paragraphs': [
                    'Adoptamos medidas técnicas y administrativas de seguridad razonables para '
                    'proteger sus datos contra el acceso no autorizado, la pérdida, la alteración o la '
                    'destrucción, incluyendo controles de acceso, cifrado de datos sensibles y '
                    'monitoreo de la plataforma.',
                ],
            },
            {
                'title': 'Transferencia a terceros',
                'icon': 'bi-people',
                'paragraphs': [
                    'Sus datos no comercializamos ni cedemos a terceros. Únicamente los compartimos con '
                    'proveedores de logística, procesamiento de pagos y envío de comunicaciones que los '
                    'tratan por cuenta de Carely, bajo acuerdos de confidencialidad y encargo de '
                    'tratamiento, o cuando la autoridad competente lo solicite dentro del marco legal '
                    'aplicable.',
                ],
            },
            {
                'title': 'Conservación y eliminación',
                'icon': 'bi-archive',
                'paragraphs': [
                    'Conservamos sus datos mientras la cuenta esté activa y, tras su deshabilitación, '
                    'por los plazos legales y contables exigidos por la normativa colombiana y por la '
                    'función probatoria, pasado el cual se eliminarán de manera segura o se bloquearán '
                    'de forma irreversible.',
                ],
            },
            {
                'title': 'Cambios y contacto',
                'icon': 'bi-envelope-paper',
                'paragraphs': [
                    'Podemos actualizar esta política en cualquier momento; los cambios se publicarán '
                    'en esta página con su fecha de actualización. Si tiene preguntas, puede escribir '
                    f'a {settings.CARELY_EMAIL} y le responderemos dentro de los plazos previstos por '
                    'la ley. Puede solicitar una copia íntegra de esta política en cualquier momento.',
                ],
            },
        ],
    },
]


class LegalView(TemplateView):
    template_name = 'core/legal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['legal_groups'] = LEGAL_GROUPS
        return context


class DashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        return redirect('catalog:home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_users'] = User.objects.count()
        context['total_products'] = Product.objects.count()
        context['total_categories'] = Category.objects.count()
        context['total_orders'] = Order.objects.count()

        context['recent_users'] = User.objects.order_by('-date_joined')[:5]
        context['recent_orders'] = Order.objects.select_related('user')[:5]
        return context