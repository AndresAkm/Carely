from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, Count
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView, ListView, UpdateView

from apps.core.permissions import is_admin

from ..forms import OrderFilterForm, OrderStatusForm
from ..models import Order


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

    def get_success_url(self):
        return reverse('dashboard:order_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, f'El pedido #{self.object.pk} se actualizó correctamente.')
        return super().form_valid(form)
