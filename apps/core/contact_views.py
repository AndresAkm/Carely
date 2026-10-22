import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from apps.core.forms import ContactReplyForm
from apps.core.models import ContactRequest
from apps.core.permissions import is_admin
from apps.core.services import send_contact_reply
from apps.users.services import GmailServiceError

logger = logging.getLogger(__name__)


class DashboardContactMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        return redirect('core:home')


class ContactRequestListView(DashboardContactMixin, ListView):
    model = ContactRequest
    template_name = 'core/dashboard/contact_request_list.html'
    context_object_name = 'contact_requests'
    paginate_by = 10

    def get_queryset(self):
        queryset = ContactRequest.objects.select_related('replied_by')
        search = self.request.GET.get('q', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(email__icontains=search)
                | Q(subject__icontains=search)
                | Q(message__icontains=search)
            )
        status = self.request.GET.get('status', '')
        if status in ContactRequest.Status.values:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_q'] = self.request.GET.get('q', '')
        context['filter_status'] = self.request.GET.get('status', '')
        context['status_choices'] = ContactRequest.Status.choices
        context['pending_count'] = ContactRequest.objects.filter(
            status=ContactRequest.Status.PENDIENTE,
        ).count()
        query = self.request.GET.copy()
        query.pop('page', None)
        context['filter_query'] = query.urlencode()
        return context


def user_contact_requests(user):
    """Solicitudes del titular, incluidas las enviadas antes de tener cuenta."""
    return ContactRequest.objects.filter(
        Q(user=user) | Q(email__iexact=user.email),
    )


class MyContactRequestListView(LoginRequiredMixin, ListView):
    model = ContactRequest
    template_name = 'core/contact_requests/my_list.html'
    context_object_name = 'contact_requests'
    paginate_by = 8

    def get_queryset(self):
        return user_contact_requests(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        context['pending_count'] = queryset.filter(
            status=ContactRequest.Status.PENDIENTE,
        ).count()
        context['total_count'] = queryset.count()
        return context


class MyContactRequestDetailView(LoginRequiredMixin, View):
    template_name = 'core/contact_requests/my_detail.html'

    def get(self, request, pk):
        contact_request = get_object_or_404(user_contact_requests(request.user), pk=pk)
        return render(
            request,
            self.template_name,
            {'contact_request': contact_request},
        )


class ContactRequestDetailView(DashboardContactMixin, View):
    template_name = 'core/dashboard/contact_request_detail.html'

    def get(self, request, pk):
        contact_request = get_object_or_404(ContactRequest, pk=pk)
        form = ContactReplyForm(initial={'reply': contact_request.reply})
        return self._render(request, contact_request, form)

    def post(self, request, pk):
        contact_request = get_object_or_404(ContactRequest, pk=pk)
        form = ContactReplyForm(request.POST)
        if not form.is_valid():
            return self._render(request, contact_request, form)

        reply = form.cleaned_data['reply']
        try:
            send_contact_reply(contact_request, reply, request.user)
        except GmailServiceError:
            logger.exception(
                'No se pudo enviar la respuesta de la solicitud #%s a %s',
                contact_request.pk,
                contact_request.email,
            )
            messages.error(
                request,
                'No pudimos enviar la respuesta en este momento. Inténtalo de nuevo.',
            )
            return self._render(request, contact_request, form)

        contact_request.reply = reply
        contact_request.status = ContactRequest.Status.RESPONDIDA
        contact_request.replied_at = timezone.now()
        contact_request.replied_by = request.user
        contact_request.save(
            update_fields=['reply', 'status', 'replied_at', 'replied_by', 'updated_at'],
        )

        messages.success(
            request,
            f'La respuesta se envió a {contact_request.email}.',
        )
        return redirect('dashboard:contact_request_detail', pk=contact_request.pk)

    def _render(self, request, contact_request, form):
        return render(
            request,
            self.template_name,
            {
                'contact_request': contact_request,
                'form': form,
            },
        )
