(function () {
  const driver = window.driver && window.driver.js && window.driver.js.driver;

  const TOURS = {
    login: [
      {
        element: '.auth-card',
        popover: {
          title: 'Bienvenida de nuevo',
          description: 'Desde aquí entras a tu cuenta de Carely con tu correo y tu contraseña.',
          side: 'bottom',
          align: 'center',
        },
      },
      {
        element: '#id_email',
        popover: {
          title: 'Correo electrónico',
          description: 'Escribe el correo con el que te registraste en Carely.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#id_password',
        popover: {
          title: 'Contraseña',
          description: 'Digita tu clave personal. Si la olvidaste, usa el enlace de recuperación.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: 'a[href*="password_reset"]',
        popover: {
          title: '¿Olvidaste tu contraseña?',
          description: 'Te enviamos un enlace seguro al correo para crear una nueva.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: 'button[type="submit"]',
        popover: {
          title: 'Iniciar sesión',
          description: 'Pulsa aquí para entrar a tu panel y a tu cuenta.',
          side: 'bottom',
          align: 'center',
        },
      },
      {
        element: 'a[href*="register"]',
        popover: {
          title: 'Crear cuenta',
          description: 'Si aún no tienes cuenta, regístrate desde aquí.',
          side: 'bottom',
          align: 'center',
        },
      },
    ],
    catalog: [
      {
        element: '#categoryTabs',
        popover: {
          title: 'Categorías',
          description: 'Elige una categoría para ver solo los productos que te interesan.',
          side: 'bottom',
          align: 'center',
        },
      },
      {
        element: '.catalog-filter-form',
        popover: {
          title: 'Filtros y búsqueda',
          description: 'Busca por nombre, marca, precio o descuento para encontrar más rápido lo que necesitas.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#productGrid',
        popover: {
          title: 'Productos',
          description: 'Cada tarjeta muestra precio, stock y acciones rápidas. Haz clic en una para ver el detalle.',
          side: 'bottom',
          align: 'center',
        },
      },
      {
        element: '.product-card',
        popover: {
          title: 'Detalle del producto',
          description: 'Abre la tarjeta para ver la descripción completa y agregar el producto al carrito.',
          side: 'bottom',
          align: 'center',
        },
      },
    ],
    product: [
      {
        element: '.product-detail-breadcrumb',
        popover: {
          title: 'Navegación',
          description: 'Puedes volver al catálogo o a la categoría desde este camino.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.product-detail-media',
        popover: {
          title: 'Imagen del producto',
          description: 'Aquí ves el producto tal como se entrega.',
          side: 'bottom',
          align: 'center',
        },
      },
      {
        element: '.product-detail-info',
        popover: {
          title: 'Información principal',
          description: 'Consulta el nombre, el precio, el stock y la descripción del producto.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#product-detail-quantity',
        popover: {
          title: 'Cantidad',
          description: 'Define cuántas unidades quieres agregar al carrito.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.product-detail-cart-form button',
        popover: {
          title: 'Agregar al carrito',
          description: 'Pulsa aquí para enviar el producto a tu carrito de compras.',
          side: 'bottom',
          align: 'center',
        },
      },
    ],
    cart: [
      {
        element: '.cart-title',
        popover: {
          title: 'Tu carrito',
          description: 'Aquí revisas los productos que elegiste antes de pagar.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.cart-table',
        popover: {
          title: 'Productos',
          description: 'Cada fila muestra el producto, el precio unitario y el subtotal.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.qty-stepper',
        popover: {
          title: 'Cantidad',
          description: 'Cambia la cantidad con los botones menos y más, o escribiéndola directamente.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.btn-remove-item',
        popover: {
          title: 'Eliminar',
          description: 'Quita un producto del carrito con este botón.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.cart-summary',
        popover: {
          title: 'Resumen',
          description: 'Aquí aparece el total de tu pedido antes de ir al pago.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.btn-checkout',
        popover: {
          title: 'Ir al pago',
          description: 'Continúa hacia el checkout para elegir dirección y método de pago.',
          side: 'bottom',
          align: 'center',
        },
      },
      {
        element: '.cart-empty',
        popover: {
          title: 'Carrito vacío',
          description: 'Aún no tienes productos. Explora el catálogo y agrega lo que necesites.',
          side: 'bottom',
          align: 'center',
        },
      },
    ],
    checkout: [
      {
        element: '.checkout-section h1',
        popover: {
          title: 'Checkout',
          description: 'Aquí confirmas tu pedido antes de ir a la pasarela de pago.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.address-selector',
        popover: {
          title: 'Dirección de envío',
          description: 'Elige una dirección guardada o agrega una nueva.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.checkout-card:nth-of-type(2)',
        popover: {
          title: 'Notas del pedido',
          description: 'Puedes dejar indicaciones para la entrega, como dejar en portería.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#couponInput',
        popover: {
          title: 'Cupón de descuento',
          description: 'Si tienes un código, escríbelo aquí y valídalo para aplicar el descuento.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.checkout-summary',
        popover: {
          title: 'Resumen del pedido',
          description: 'Revisa los productos, el descuento y el total antes de confirmar.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#btnConfirm',
        popover: {
          title: 'Pagar con Wompi',
          description: 'Confirma el pedido y serás redirigido a la pasarela de pago segura.',
          side: 'bottom',
          align: 'center',
        },
      },
    ],
    orders: [
      {
        element: 'h1',
        popover: {
          title: 'Mis pedidos',
          description: 'Aquí consultas el historial de tus compras en Carely.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.order-row',
        popover: {
          title: 'Pedidos',
          description: 'Cada tarjeta muestra la fecha, el estado y el total de un pedido.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.badge',
        popover: {
          title: 'Estado',
          description: 'El pedido puede estar pendiente, confirmado, enviado, entregado o cancelado.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: 'a[href*="order_detail"]',
        popover: {
          title: 'Ver detalle',
          description: 'Abre el pedido para revisar los productos y la dirección de envío.',
          side: 'bottom',
          align: 'start',
        },
      },
    ],
    'order-detail': [
      {
        element: '.order-ship',
        popover: {
          title: 'Entrega',
          description: 'Aquí aparece la dirección de envío y las instrucciones que dejaste.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.order-timeline',
        popover: {
          title: 'Seguimiento',
          description: 'Consulta el historial de estados del pedido.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: 'table',
        popover: {
          title: 'Productos',
          description: 'Revisa los artículos, la cantidad y el subtotal de cada uno.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.c-btn--primary',
        popover: {
          title: 'Reintentar pago',
          description: 'Si el pedido está pendiente, puedes pagar desde aquí.',
          side: 'bottom',
          align: 'start',
        },
      },
    ],
    profile: [
      {
        element: '.profile-subnav',
        popover: {
          title: 'Tu cuenta',
          description: 'Desde aquí saltas a tus datos, seguridad y apariencia.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.profile-hero',
        popover: {
          title: 'Resumen',
          description: 'Aquí ves tu nombre, tu correo y si tienes la verificación en dos pasos activa.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#perfil-datos',
        popover: {
          title: 'Información personal',
          description: 'Actualiza tu nombre, teléfono y correo de contacto.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#perfil-seguridad',
        popover: {
          title: 'Seguridad',
          description: 'Cambia tu contraseña o activa la verificación en dos pasos.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#perfil-apariencia',
        popover: {
          title: 'Apariencia',
          description: 'Elige el color de Carely que prefieras.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.profile-danger',
        popover: {
          title: 'Zona de peligro',
          description: 'Aquí puedes deshabilitar tu cuenta si lo necesitas.',
          side: 'bottom',
          align: 'start',
        },
      },
    ],
    addresses: [
      {
        element: '.profile-header',
        popover: {
          title: 'Mis direcciones',
          description: 'Gestiona las direcciones donde quieres recibir tus pedidos.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.profile-summary',
        popover: {
          title: 'Resumen',
          description: 'Aquí aparece cuántas direcciones tienes registradas.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.profile-card',
        popover: {
          title: 'Direcciones',
          description: 'Cada tarjeta muestra una dirección con sus acciones: editar, eliminar o marcar como predeterminada.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: 'a[href*="address_create"]',
        popover: {
          title: 'Nueva dirección',
          description: 'Agrega otra dirección de envío desde aquí.',
          side: 'bottom',
          align: 'start',
        },
      },
    ],
    'two-factor': [
      {
        element: '.profile-header',
        popover: {
          title: 'Verificación en dos pasos',
          description: 'Aquí activas o desactivas el código de seguridad por correo.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.profile-card',
        popover: {
          title: 'Estado',
          description: 'Revisa si la verificación está activa y qué necesitas para usarla.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.profile-form',
        popover: {
          title: 'Código de verificación',
          description: 'Escribe el código que te enviamos al correo para confirmar la acción.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.profile-form-actions',
        popover: {
          title: 'Confirmar',
          description: 'Pulsa aquí para activar o desactivar la verificación en dos pasos.',
          side: 'bottom',
          align: 'start',
        },
      },
    ],
    dashboard: [
      {
        element: '#sidebar',
        popover: {
          title: 'Menú del panel',
          description: 'Desde aquí entras a productos, categorías, pedidos, usuarios, cupones, reportes y personalización web.',
          side: 'right',
          align: 'start',
        },
      },
      {
        element: '.dashboard-topbar',
        popover: {
          title: 'Barra superior',
          description: 'Consulta la tienda en vivo o cierra sesión desde aquí.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.stat-card',
        popover: {
          title: 'Resumen',
          description: 'Estas tarjetas muestran cuántos productos, usuarios, categorías y pedidos hay en la tienda.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.feature-card',
        popover: {
          title: 'Accesos rápidos',
          description: 'Entra a las secciones más usadas del panel desde estas tarjetas.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#sidebar a[href*="personalizacion"]',
        popover: {
          title: 'Personalización web',
          description: 'Abre esta sección para editar la portada, los destacados, los beneficios, el pie de página y los logos.',
          side: 'right',
          align: 'start',
        },
      },
      {
        element: '#dashboard-recent-users',
        popover: {
          title: 'Usuarios recientes',
          description: 'Aquí aparecen los últimos usuarios registrados en la tienda.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#dashboard-recent-orders',
        popover: {
          title: 'Pedidos recientes',
          description: 'Consulta las últimas órdenes recibidas y su estado actual.',
          side: 'bottom',
          align: 'start',
        },
      },
    ],
    'site-customization': [
      {
        element: '.dashboard-page-header',
        popover: {
          title: 'Personalización web',
          description: 'Desde esta pantalla controlas la identidad y el contenido visible en la landing de Carely.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.bento-card--hero',
        popover: {
          title: 'Portada',
          description: 'Cambia el título, el subtítulo, el texto del botón y la imagen principal de la página de inicio.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.bento-card--categories',
        popover: {
          title: 'Categorías destacadas',
          description: 'Elige qué categorías quieres mostrar en la portada.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.bento-card--products',
        popover: {
          title: 'Productos destacados',
          description: 'Busca, filtra y selecciona los productos que aparecerán en la página de inicio.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.bento-card--benefits',
        popover: {
          title: 'Beneficios',
          description: 'Edita los mensajes de valor que se muestran debajo de la portada.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.bento-card--footer',
        popover: {
          title: 'Pie de página',
          description: 'Actualiza los datos de contacto y las redes sociales del sitio.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.bento-card--logos',
        popover: {
          title: 'Logos',
          description: 'Reemplaza el logo principal y el isotipo que se muestran en toda la tienda.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '.bento-actions-card',
        popover: {
          title: 'Guardar cambios',
          description: 'Descarta los cambios o publícalos de inmediato en la tienda.',
          side: 'bottom',
          align: 'start',
        },
      },
    ],
  };

  const CONFIG = {
    animate: true,
    duration: 350,
    overlayColor: '#1A1A1A',
    overlayOpacity: 0.72,
    stagePadding: 8,
    stageRadius: 12,
    popoverOffset: 14,
    popoverClass: 'carely-popover',
    showProgress: true,
    progressText: '{{current}} de {{total}}',
    nextBtnText: 'Siguiente',
    prevBtnText: 'Atrás',
    doneBtnText: 'Entendido',
    closeBtnLabel: 'Cerrar',
    allowClose: true,
    overlayClickBehavior: 'close',
    smoothScroll: true,
    allowScroll: true,
    skipMissingElement: false,
  };

  function createHelpButton(steps) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'tour-help-btn';
    button.setAttribute('aria-label', 'Iniciar guía');
    button.setAttribute('title', 'Iniciar guía');
    button.innerHTML = '<i class="bi bi-question-lg"></i>';

    button.addEventListener('click', function () {
      const driverObj = driver({ ...CONFIG, steps });
      driverObj.drive();
    });

    document.body.appendChild(button);
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!driver) {
      return;
    }

    const target = document.querySelector('[data-tour]');
    if (!target) {
      return;
    }

    const key = target.getAttribute('data-tour');
    const steps = TOURS[key];
    if (!steps) {
      return;
    }

    createHelpButton(steps);
  });
})();
