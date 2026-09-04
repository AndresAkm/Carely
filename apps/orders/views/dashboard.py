from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, DeleteView, ListView, UpdateView

from apps.core.permissions import is_admin

from ..forms import CouponForm, OrderFilterForm, OrderStatusForm, OrderNotesForm
from ..models import Coupon, Order, OrderStatusHistory


class DashboardOrderMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        return redirect('core:home')


class OrderListView(DashboardOrderMixin, ListView):
    model = Order
    template_name = 'orders/dashboard/order_list.html'
    context_object_name = 'orders'
    paginate_by = 8

    def get_queryset(self):
        queryset = Order.objects.select_related('user').annotate(item_count=Count('items')).order_by('-created_at')
        self.filter_form = OrderFilterForm(self.request.GET or None)
        if not self.filter_form.is_valid():
            return queryset

        filters = self.filter_form.cleaned_data
        search = filters.get('q')
        if search:
            search_filter = Q(user__first_name__icontains=search)
            search_filter |= Q(user__last_name__icontains=search)
            search_filter |= Q(user__email__icontains=search)
            if search.isdigit():
                search_filter |= Q(pk=int(search))
            queryset = queryset.filter(search_filter)
        if filters.get('status'):
            queryset = queryset.filter(status=filters['status'])
        if filters.get('created_from'):
            queryset = queryset.filter(created_at__date__gte=filters['created_from'])
        if filters.get('created_to'):
            queryset = queryset.filter(created_at__date__lte=filters['created_to'])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = getattr(self, 'filter_form', OrderFilterForm(self.request.GET or None))
        query = self.request.GET.copy()
        query.pop('page', None)
        context['filter_query'] = query.urlencode()
        return context


class OrderDetailView(DashboardOrderMixin, DetailView):
    model = Order
    template_name = 'orders/dashboard/order_detail.html'
    context_object_name = 'order'

    def get_queryset(self):
        return Order.objects.select_related('user').prefetch_related('items__product', 'payments')


class OrderStatusUpdateView(DashboardOrderMixin, UpdateView):
    model = Order
    form_class = OrderStatusForm
    template_name = 'orders/dashboard/order_status_form.html'
    context_object_name = 'order'

    def get_queryset(self):
        return Order.objects.select_related('user').prefetch_related('status_history')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object

        # Construir mapa status → fecha (primera aparición)
        history_map = {}
        for entry in order.status_history.order_by('created_at'):
            if entry.status not in history_map:
                history_map[entry.status] = entry.created_at

        # Pedidos recién creados no tienen historial aún → usar created_at como fecha de pendiente
        if Order.Status.PENDIENTE not in history_map and order.status == Order.Status.PENDIENTE:
            history_map[Order.Status.PENDIENTE] = order.created_at

        context['status_history_map'] = history_map
        context['can_advance'] = (
            order.status in STATUS_ORDER and
            order.status != Order.Status.ENTREGADO
        )
        context['is_cancelled'] = order.status == Order.Status.CANCELADO
        context['is_delivered'] = order.status == Order.Status.ENTREGADO
        return context

    def get_success_url(self):
        return reverse(
            'dashboard:order_status',
            kwargs={'pk': self.object.pk}
        )

    def form_valid(self, form):
        old_status = self.object.status

        response = super().form_valid(form)

        new_status = self.object.status
        comment = form.cleaned_data.get('notes', '').strip()

        if old_status != new_status or comment:
            OrderStatusHistory.objects.create(
                order=self.object,
                status=new_status,
                comment=comment,
                changed_by=self.request.user,
            )

        messages.success(
            self.request,
            f'El pedido #{self.object.pk} se actualizó correctamente.'
        )

        return response



# ─────────────────────────────────────────────────────────────────────────────
# CUPONES
# ─────────────────────────────────────────────────────────────────────────────

class DashboardCouponMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        return redirect('core:home')


class CouponListView(DashboardCouponMixin, ListView):
    model = Coupon
    template_name = 'orders/dashboard/coupon_list.html'
    context_object_name = 'coupons'
    paginate_by = 10
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Coupon.objects.order_by('-created_at')
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(code__icontains=q) | Q(discount_type__icontains=q)
            )
        is_active = self.request.GET.get('is_active', '')
        if is_active in ('1', '0'):
            queryset = queryset.filter(is_active=is_active == '1')
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_q'] = self.request.GET.get('q', '')
        ctx['filter_active'] = self.request.GET.get('is_active', '')
        ctx['now'] = timezone.now()
        return ctx


class CouponCreateView(DashboardCouponMixin, CreateView):
    model = Coupon
    form_class = CouponForm
    template_name = 'orders/dashboard/coupon_form.html'
    success_url = reverse_lazy('dashboard:coupon_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Cupón "{self.object.code}" creado correctamente.')
        return response


class CouponUpdateView(DashboardCouponMixin, UpdateView):
    model = Coupon
    form_class = CouponForm
    template_name = 'orders/dashboard/coupon_form.html'
    success_url = reverse_lazy('dashboard:coupon_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Cupón "{self.object.code}" actualizado correctamente.')
        return response


class CouponToggleActiveView(DashboardCouponMixin, View):
    """Activa o desactiva un cupón via POST (sin formulario complejo)."""

    def post(self, request, pk):
        coupon = get_object_or_404(Coupon, pk=pk)
        coupon.is_active = not coupon.is_active
        coupon.save(update_fields=['is_active'])
        state = 'activado' if coupon.is_active else 'desactivado'
        messages.success(request, f'Cupón "{coupon.code}" {state}.')
        return redirect('dashboard:coupon_list')


class CouponDeleteView(DashboardCouponMixin, DeleteView):
    """
    Eliminación segura de cupones.

    ON DELETE SET NULL en Order.coupon garantiza que los pedidos existentes
    conservan su snapshot (coupon_code + discount_amount) aunque el cupón
    sea eliminado. No se pierde historial.
    """
    model = Coupon
    template_name = 'orders/dashboard/coupon_confirm_delete.html'
    success_url = reverse_lazy('dashboard:coupon_list')

    def form_valid(self, form):
        code = self.object.code
        response = super().form_valid(form)
        messages.success(self.request, f'Cupón "{code}" eliminado correctamente.')
        return response


# ─────────────────────────────────────────────────────────────────────────────
# NUEVOS ENDPOINTS PARA EL TIMELINE DE ESTADOS
# ─────────────────────────────────────────────────────────────────────────────

from django.views import View
from django.shortcuts import get_object_or_404, redirect
from apps.orders.models import OrderStatusHistory

STATUS_ORDER = [
    Order.Status.PENDIENTE,
    Order.Status.CONFIRMADO,
    Order.Status.ENVIADO,
    Order.Status.ENTREGADO
]

class OrderAdvanceStatusView(DashboardOrderMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        
        if order.status == Order.Status.CANCELADO:
            messages.error(request, 'No se puede avanzar un pedido cancelado.')
            return redirect('dashboard:order_status', pk=order.pk)
            
        if order.status == Order.Status.ENTREGADO:
            messages.error(request, 'El pedido ya está entregado.')
            return redirect('dashboard:order_status', pk=order.pk)
            
        try:
            current_index = STATUS_ORDER.index(order.status)
            new_status = STATUS_ORDER[current_index + 1]
            
            order.status = new_status
            order.save(update_fields=['status'])
            
            OrderStatusHistory.objects.create(
                order=order,
                status=new_status,
                comment='Estado avanzado desde el panel',
                changed_by=request.user
            )
            messages.success(request, f'El pedido avanzó a {order.get_status_display()}.')
        except ValueError:
            messages.error(request, 'Estado actual no válido para avanzar.')
            
        return redirect('dashboard:order_status', pk=order.pk)


class OrderCancelView(DashboardOrderMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        
        if order.status in [Order.Status.ENTREGADO, Order.Status.CANCELADO]:
            messages.error(request, 'No se puede cancelar en este estado.')
            return redirect('dashboard:order_status', pk=order.pk)
            
        reason = request.POST.get('cancel_reason', '').strip()
        
        order.status = Order.Status.CANCELADO
        order.save(update_fields=['status'])
        
        OrderStatusHistory.objects.create(
            order=order,
            status=Order.Status.CANCELADO,
            comment=f"Cancelado por admin. {reason}".strip(),
            changed_by=request.user
        )
        
        messages.success(request, 'El pedido fue cancelado correctamente.')
        return redirect('dashboard:order_status', pk=order.pk)


class OrderUpdateNotesView(DashboardOrderMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        notes = request.POST.get('notes', '').strip()
        
        order.notes = notes
        order.save(update_fields=['notes'])
        
        messages.success(request, 'Las notas se actualizaron correctamente.')
        return redirect('dashboard:order_status', pk=order.pk)
