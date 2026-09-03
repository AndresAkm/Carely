from io import BytesIO
import os
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView, View
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    from svglib.svglib import svg2rlg
except ImportError:
    svg2rlg = None

from apps.core.forms import ReportFilterForm
from apps.core.permissions import is_admin
from apps.orders.models import Order, OrderItem


def get_report_orders(request):
    form = ReportFilterForm(request.GET or None)
    orders = Order.objects.all()
    if form.is_valid():
        filters = form.cleaned_data
        if filters.get('created_from'):
            orders = orders.filter(created_at__date__gte=filters['created_from'])
        if filters.get('created_to'):
            orders = orders.filter(created_at__date__lte=filters['created_to'])
        if filters.get('status'):
            orders = orders.filter(status=filters['status'])
    return form, orders


def get_report_data(request):
    filter_form, orders = get_report_orders(request)
    sale_orders = orders.exclude(status=Order.Status.CANCELADO)
    zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=14, decimal_places=2))
    totals = sale_orders.aggregate(
        revenue=Coalesce(Sum('total'), zero),
        average=Avg('total'),
    )

    status_labels = dict(Order.Status.choices)
    status_summary = [
        {
            'label': status_labels.get(row['status'], row['status']),
            'status': row['status'],
            'count': row['count'],
            'total': row['total'] or Decimal('0.00'),
        }
        for row in orders.values('status').annotate(
            count=Count('id'),
            total=Sum('total'),
        ).order_by('status')
    ]

    top_products = OrderItem.objects.filter(order__in=sale_orders).annotate(
        line_total=ExpressionWrapper(
            F('quantity') * F('unit_price'),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
    ).values('product__name').annotate(
        quantity=Sum('quantity'),
        revenue=Sum('line_total'),
    ).order_by('-revenue', 'product__name')[:10]

    daily_sales = sale_orders.annotate(day=TruncDate('created_at')).values('day').annotate(
        orders=Count('id'),
        revenue=Sum('total'),
    ).order_by('-day')[:30]

    return {
        'report_form': filter_form,
        'orders': orders,
        'sale_orders': sale_orders,
        'report_total_orders': orders.count(),
        'report_sales_orders': sale_orders.count(),
        'report_revenue': totals['revenue'],
        'report_average_order': totals['average'] or Decimal('0.00'),
        'report_pending_orders': orders.filter(status=Order.Status.PENDIENTE).count(),
        'status_summary': status_summary,
        'top_products': top_products,
        'daily_sales': daily_sales,
    }


class DashboardReportMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        return redirect('core:home')


class ReportView(DashboardReportMixin, TemplateView):
    template_name = 'core/dashboard/report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_report_data(self.request))
        return context


class ReportExportView(DashboardReportMixin, View):
    def get(self, request, *args, **kwargs):
        data = get_report_data(request)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='ReportTitle', parent=styles['Title'], fontName='Helvetica-Bold',
            fontSize=18, leading=22, textColor=colors.HexColor('#1A1A1A'),
            alignment=TA_CENTER, spaceAfter=5 * mm,
        ))
        styles.add(ParagraphStyle(
            name='ReportSection', parent=styles['Heading2'], fontName='Helvetica-Bold',
            fontSize=11, leading=14, textColor=colors.HexColor('#5B8DEF'),
            spaceBefore=5 * mm, spaceAfter=2 * mm,
        ))
        styles.add(ParagraphStyle(
            name='ReportCell', parent=styles['BodyText'], fontName='Helvetica',
            fontSize=8, leading=10, textColor=colors.HexColor('#1A1A1A'),
        ))
        styles.add(ParagraphStyle(
            name='ReportCellRight', parent=styles['ReportCell'], alignment=TA_RIGHT,
        ))

        def money(value):
            return f'${value or Decimal("0.00"):,.2f}'

        def cell(value, style='ReportCell'):
            return Paragraph(str(value), styles[style])

        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
            title='Reporte de pedidos Carely',
            author='Carely',
        )
        story = []

        if svg2rlg:
            logo_path = os.path.join(settings.BASE_DIR, 'apps', 'core', 'static', 'core', 'images', 'carely-logo.svg')
            if os.path.exists(logo_path):
                drawing = svg2rlg(logo_path)
                if drawing:
                    scale_factor = 0.45
                    drawing.width = drawing.width * scale_factor
                    drawing.height = drawing.height * scale_factor
                    drawing.scale(scale_factor, scale_factor)
                    drawing.hAlign = 'CENTER'
                    story.append(drawing)
                    story.append(Spacer(1, 4 * mm))

        story.append(Paragraph('Reporte de pedidos', styles['ReportTitle']))
        form = data['report_form']
        selected_filters = []
        if form.is_valid():
            filters = form.cleaned_data
            if filters.get('created_from'):
                selected_filters.append(f"Desde: {filters['created_from'].strftime('%d/%m/%Y')}")
            if filters.get('created_to'):
                selected_filters.append(f"Hasta: {filters['created_to'].strftime('%d/%m/%Y')}")
            if filters.get('status'):
                selected_filters.append(f"Estado: {dict(Order.Status.choices)[filters['status']]}")
        story.append(Paragraph(
            'Filtros: ' + ', '.join(selected_filters) if selected_filters else 'Filtros: todos los pedidos',
            styles['ReportCell'],
        ))
        story.append(Spacer(1, 3 * mm)) 

        summary = [
            [cell('Pedidos'), cell('Ventas no canceladas'), cell('Ticket promedio'), cell('Pendientes')],
            [cell(data['report_total_orders']), cell(money(data['report_revenue'])), cell(money(data['report_average_order'])), cell(data['report_pending_orders'])],
        ]
        summary_table = Table(summary, colWidths=[42 * mm] * 4)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5F0F8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1A1A1A')),
            ('GRID', (0, 0), (-1, -1), .35, colors.HexColor('#E8E3EE')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))
        story.extend([summary_table, Paragraph('Detalle de pedidos', styles['ReportSection'])])

        orders_table_data = [[cell('Pedido'), cell('Cliente'), cell('Estado'), cell('Total', 'ReportCellRight'), cell('Fecha')]]
        for order in data['orders'].select_related('user').order_by('-created_at'):
            orders_table_data.append([
                cell(f'#{order.pk}'),
                cell(order.user.get_full_name() or order.user.email),
                cell(order.get_status_display()),
                cell(money(order.total), 'ReportCellRight'),
                cell(order.created_at.strftime('%d/%m/%Y %H:%M') if order.created_at else 'N/A'),
            ])
        orders_table = Table(orders_table_data, colWidths=[18 * mm, 65 * mm, 32 * mm, 27 * mm, 35 * mm], repeatRows=1)
        orders_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A1A1A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), .3, colors.HexColor('#E8E3EE')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEFCFD')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(orders_table)

        story.append(Paragraph('Ventas por día', styles['ReportSection']))
        daily_table_data = [[cell('Fecha'), cell('Pedidos'), cell('Ventas', 'ReportCellRight')]]
        for row in data['daily_sales']:
            date_str = row['day'].strftime('%d/%m/%Y') if row['day'] else 'N/A'
            daily_table_data.append([cell(date_str), cell(row['orders']), cell(money(row['revenue']), 'ReportCellRight')])
        daily_table = Table(daily_table_data, colWidths=[60 * mm, 40 * mm, 50 * mm], repeatRows=1)
        daily_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5F0F8')),
            ('GRID', (0, 0), (-1, -1), .3, colors.HexColor('#E8E3EE')),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(daily_table)

        story.append(Paragraph('Productos más vendidos', styles['ReportSection']))
        products_table_data = [[cell('Producto'), cell('Cantidad'), cell('Ingresos', 'ReportCellRight')]]
        for product in data['top_products']:
            products_table_data.append([cell(product['product__name']), cell(product['quantity']), cell(money(product['revenue']), 'ReportCellRight')])
        products_table = Table(products_table_data, colWidths=[90 * mm, 30 * mm, 50 * mm], repeatRows=1)
        products_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5F0F8')),
            ('GRID', (0, 0), (-1, -1), .3, colors.HexColor('#E8E3EE')),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(products_table)
        document.build(story)

        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="reporte-pedidos.pdf"'
        return response
