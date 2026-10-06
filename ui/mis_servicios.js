'use strict';
const $ = id => document.getElementById(id);
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.has('sesion'))
  sessionStorage.setItem('nucleo-session', fragment.get('sesion'));
const callback = fragment.get('conectado');
history.replaceState(null, '', '/');
let servicios = [], actual = null, paso = 1, editing = '', ocupado = false,
    emailsConocidos = [], perfilActual = null;
let draft = null;
try {
  draft = JSON.parse(sessionStorage.getItem('nucleo-draft') || 'null');
} catch {
  sessionStorage.removeItem('nucleo-draft');
}
const estados = {
  guardada : 'Guardada · falta comprobar',
  acceso_comprobado : 'Acceso comprobado',
  sin_verificar : 'Pendiente de comprobar',
  sin_conexion : 'No se pudo contactar',
  clave_rechazada : 'Clave rechazada',
  sin_permiso : 'Revisar permisos',
  sin_saldo : 'Revisar saldo',
  limite : 'Límite alcanzado',
  no_disponible : 'Servicio no disponible',
  pendiente : 'Falta autorizar',
  otra_cuenta : 'Revisar cuenta',
  sin_modelos : 'Faltan modelos locales'
};
function el(tag, text, cls) {
  const e = document.createElement(tag);
  if (text !== undefined)
    e.textContent = text;
  if (cls)
    e.className = cls;
  return e;
}
function btn(text, fn, cls = 'primary') {
  const b = el('button', text, cls);
  b.type = 'button';
  b.onclick = fn;
  return b;
}
function link(text, url, cls = 'primary') {
  const a = el('a', text, cls);
  a.href = url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  return a;
}
function note(text, good = false) {
  return el('div', text, 'notice-inline' + (good ? ' success' : ''));
}
function notice(text) {
  $('notice').textContent = text;
  $('notice').hidden = false;
}
async function api(path, data) {
  const opts = {
    headers :
        {'X-Nucleo-Session' : sessionStorage.getItem('nucleo-session') || ''}
  };
  if (data !== undefined) {
    opts.method = 'POST';
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(data);
  }
  let r;
  try {
    r = await fetch(path, opts);
  } catch (e) {
    throw new Error(
        'No pudimos contactar al asistente. Abrí nuevamente Mis servicios desde su acceso directo.');
  }
  const res = await r.json();
  if (!r.ok)
    throw new Error(res.mensaje || 'No se pudo completar la acción.');
  return res;
}
async function ejecutar(fn) {
  if (ocupado)
    return;
  ocupado = true;
  document.body.setAttribute('aria-busy', 'true');
  const buttons = [...document.querySelectorAll('button') ];
  buttons.forEach(b => b.disabled = true);
  $('notice').hidden = true;
  try {
    await fn();
  } catch (e) {
    notice(e.message);
  } finally {
    ocupado = false;
    document.body.removeAttribute('aria-busy');
    buttons.forEach(b => b.disabled = false);
  }
}
async function cargar() {
  const data = await api('/api/servicios');
  servicios = data.servicios;
  // Los proveedores opcionales se mantienen fuera del catálogo gratuito:
  // aparecen en una sección separada y no entran en rankings ni rutas por
  // el solo hecho de estar visibles.
  try {
    const opcionales = await api('/api/proveedores-opcionales');
    servicios = servicios.concat((opcionales.servicios || []).map(s => ({...s, opcional: true})));
  } catch (e) {
    // Una versión antigua del backend puede no tener todavía esta ruta.
  }
  // Permite mostrar la tarjeta aunque el asistente ya estuviera abierto
  // antes de actualizar el catálogo. Al reiniciar el asistente, el backend
  // también queda actualizado y habilita el guardado de la cuenta.
  if (!servicios.some(s => s.id === 'elevenlabs')) {
    servicios.push({
      id: 'elevenlabs', nombre: 'ElevenLabs', iniciales: 'EL',
      descripcion: 'Voz natural para convertir texto en audio. Este servicio solo se usa para TTS; no participa en chat ni en el ranking general.',
      url: 'https://elevenlabs.io', claves: 'https://elevenlabs.io/app/settings/api-keys', capacidades: ['TTS', 'Música'],
      ayuda: 'https://elevenlabs.io/docs/api-reference/text-to-speech/convert',
      pasos: ['Entrá o registrate en ElevenLabs.', 'En API Keys, elegí “Create API Key” y copiá la clave completa.', 'Volvé acá, pegá la clave y, si querés, indicá el ID de la voz que vas a usar.'],
      nota: 'Uso exclusivo: texto a voz. Requiere API key, voice ID y cuota de ElevenLabs. No habilita ninguna otra función.',
      solo_tts: true, capacidades: ['TTS'], cuentas: [], catalogo_local: true
    });
  }
  const capacidadesConocidas = {
    ollama: ['Herramientas', 'Razonamiento'], groq: ['Transcripción', 'TTS'],
    openrouter: ['Visión'], nvidia: ['Visión', 'Razonamiento'],
    google: ['Visión', 'TTS', 'Imágenes', 'Video'],
    cloudflare: ['Visión', 'Transcripción', 'TTS', 'Imágenes', 'Embeddings'],
    cohere: ['Visión', 'Transcripción', 'Embeddings'],
    siliconflow: ['Visión', 'Transcripción', 'TTS', 'Imágenes', 'Video', 'Embeddings'],
    zhipu: ['Imágenes', 'Video'], tokenrouter: ['Visión', 'TTS', 'Imágenes', 'Video'],
    xkiro: ['Visión', 'TTS', 'Imágenes'], tokenharbor: ['Visión'], elevenlabs: ['TTS', 'Música']
  };
  for (const servicio of servicios) {
    if (!Array.isArray(servicio.capacidades) || !servicio.capacidades.length)
      servicio.capacidades = capacidadesConocidas[servicio.id] || [];
    // Todos los proveedores generales se incorporaron para trabajar con
    // agentes: pueden ofrecer herramientas y razonamiento según el modelo.
    if (!servicio.solo_tts) {
      for (const capacidad of ['Herramientas', 'Razonamiento'])
        if (!servicio.capacidades.includes(capacidad)) servicio.capacidades.push(capacidad);
    }
  }
  emailsConocidos = data.emails_conocidos || [];
  const dl = $('lista-emails-conocidos');
  if (dl) {
    dl.replaceChildren();
    for (const m of emailsConocidos) {
      const opt = document.createElement('option');
      opt.value = m;
      dl.append(opt);
    }
  }
  $('os').textContent = '· ' + data.sistema;
  $('count').textContent = servicios.filter(s => s.cuentas.length).length;
  pintarTarjetas();
  await cargarPerfil();
}
async function cargarPerfil() {
  perfilActual = await api('/api/perfil');
  $('profile-name').textContent = 'Modo ' + perfilActual.nombre;
  $('profile-summary').textContent = perfilActual.perfil === 'profesional'
      ? (perfilActual.protegido
             ? (perfilActual.acceso_red ? 'Protección activa para acceso autorizado por red.' : 'Protección profesional activa en esta computadora.')
             : 'La configuración profesional necesita revisión.')
      : 'Acceso local sencillo en esta computadora.';
  $('profile-dot').className = 'profile-dot' +
      (perfilActual.perfil === 'profesional' ? ' professional' : '') +
      (perfilActual.avisos.length ? ' warning' : '');
}
function pintarTarjetas() {
  const grid = $('cards');
  const optionalGrid = $('optional-cards');
  grid.replaceChildren();
  optionalGrid.replaceChildren();
  // Los proveedores opcionales con varias cuentas habilitadas se muestran
  // junto a los servicios generales para que sean fáciles de encontrar.
  // Este cambio de ubicación no altera su activación ni sus precios. GitHub
  // queda excluido explícitamente.
  const tieneVariasCuentasActivas = s =>
      s.id !== 'github' &&
      (s.cuentas || []).filter(c => c.habilitado !== false).length > 1;
  const visibles = servicios.filter(s => !s.opcional || tieneVariasCuentasActivas(s));
  const opcionales = servicios.filter(s => s.opcional && !tieneVariasCuentasActivas(s));
  for (const s of [...visibles, ...opcionales]) {
    const card = el('article', undefined, 'card');
    if (s.solo_tts)
      card.classList.add('secondary-only');
    if (s.opcional)
      card.classList.add('optional-provider');
    const head = el('div', undefined, 'card-heading');
    head.append(el('div', s.iniciales, 'service-icon'), el('h3', s.nombre));
    if (s.solo_tts)
      head.append(el('span', 'SOLO TTS', 'service-scope-badge'));
    if (s.opcional && tieneVariasCuentasActivas(s))
      head.append(el('span', 'VARIAS CUENTAS ACTIVAS', 'service-scope-badge'));
    else if (s.opcional)
      head.append(el('span', s.habilitado ? 'OPCIONAL · ACTIVO' : 'OPCIONAL · DESACTIVADO', 'service-scope-badge'));
    card.append(head, el('p', s.descripcion));
    if (s.nota)
      card.append(note(s.nota));
    if (Array.isArray(s.capacidades) && s.capacidades.length) {
      const caps = el('div', undefined, 'capability-list');
      for (const capacidad of s.capacidades)
        caps.append(el('span', capacidad, 'capability-badge capability-' + capacidad.toLowerCase().replace(/[^a-záéíóúüñ]+/g, '-')));
      card.append(caps);
    }
    if (s.variantes_capacidades && Object.keys(s.variantes_capacidades).length) {
      const details = el('details', undefined, 'capability-variants');
      details.append(el('summary', 'Ver modelos y variantes de esta API'));
      for (const [capability, models] of Object.entries(s.variantes_capacidades)) {
        details.append(el('strong', capability.replaceAll('_', ' ')));
        details.append(el('small', models.join(' · ')));
      }
      if (Array.isArray(s.permisos_gestion) && s.permisos_gestion.length)
        details.append(el('small', 'Permisos administrativos (no participan en rankings): ' + s.permisos_gestion.join(', ')));
      if (Array.isArray(s.adaptadores_implementados)) {
        const pending = (s.capacidades_ids || []).filter(x => !s.adaptadores_implementados.includes(x));
        details.append(el('small', 'Adaptadores utilizables ahora: ' + s.adaptadores_implementados.join(', ')));
        if (pending.length) details.append(el('small', 'Catalogadas, todavía sin adaptador: ' + pending.join(', ')));
      }
      if (Array.isArray(s.no_api) && s.no_api.length)
        details.append(el('small', 'Sin adaptador API oficial disponible: ' + s.no_api.join(', ')));
      card.append(details);
    }
    const bottom = el('div', undefined, 'card-bottom');
    const verified = s.cuentas.some(c => c.estado === 'acceso_comprobado');
    const status =
        s.cuentas.length
            ? `${s.cuentas.length} cuenta${
                  s.cuentas.length === 1
                      ? ''
                      : 's'} guardada${s.cuentas.length === 1 ? '' : 's'} · ${
                  verified ? 'acceso comprobado' : 'por comprobar'}`
            : 'Sin conectar';
    if (s.opcional) {
      const enabled = s.habilitado === true;
      bottom.append(btn(enabled ? 'Desactivar proveedor' : 'Activar proveedor', () => ejecutar(async () => {
        await api('/api/proveedores-opcionales/configurar', {proveedor: s.id, habilitado: !enabled});
        notice(!enabled ? 'Proveedor activado. Todavía debés habilitar una cuenta y capacidad.' : 'Proveedor desactivado.');
        await cargar();
      }), enabled ? 'secondary service-toggle' : 'primary service-toggle'));
    }
    bottom.append(el('span', status,
                     'status' + (verified           ? ' good'
                                 : s.cuentas.length ? ' warn'
                                                    : '')),
                  btn(s.cuentas.length ? 'Ver mis cuentas  →' : 'Conectar  →',
                      () => abrirServicio(s.id), 'secondary'));
    card.append(bottom);
    (s.opcional && !tieneVariasCuentasActivas(s) ? optionalGrid : grid).append(card);
  }
}
function recordar() {
  sessionStorage.setItem('nucleo-draft',
                         JSON.stringify({id : actual.id, paso, editing}));
}
function abrirServicio(id, forceNew = false) {
  actual = servicios.find(s => s.id === id);
  if (!actual)
    return;
  editing = '';
  paso = 1;
  $('inicio').hidden = true;
  $('wizard').hidden = false;
  $('wizard-title').textContent = actual.nombre;
  $('wizard-icon').textContent = actual.iniciales;
  $('notice').hidden = true;
  if (actual.cuentas.length && !forceNew)
    cuentas();
  else
    cuentaPaso();
  if (actual.catalogo_local)
    notice('Cerrá y volvé a iniciar “Mis servicios” para habilitar el guardado de ElevenLabs en esta instancia.');
  $('wizard-title').focus();
}
function actualizarAyudaLateral() {
  const sHelp = $('service-specific-help');
  if (!sHelp)
    return;
  sHelp.replaceChildren();
  if (actual && actual.id === 'cloudflare') {
    const box = el('div', undefined, 'cf-help-box');
    box.append(el('h4', '🆔 Identificador de Cloudflare (Account ID)'));
    box.append(el(
        'p',
        'Para usar Workers AI, Cloudflare pide tu Account ID: son 32 letras y números (no es tu correo ni contraseña).'));
    const directLink =
        link('👉 Abrir Workers & Pages en Cloudflare ↗',
             'https://dash.cloudflare.com/?to=/:account/workers-and-pages');
    directLink.style.display = 'inline-block';
    directLink.style.margin = '6px 0';
    box.append(directLink);
    box.append(el('p', 'Cómo sacarlo y copiarlo:'));
    const p1 = el('p');
    p1.innerHTML =
        '<b>1. Enlace de tu navegador:</b> Al abrir el enlace de arriba, mirá la barra de direcciones arriba en tu navegador. Aparece entre <code>dash.cloudflare.com/</code> y <code>/workers-and-pages</code>. Esas 32 letras/números son tu ID. Podés copiarlo de ahí (o si pegás toda la dirección web en el campo del formulario, nosotros sacamos los 32 caracteres solos).';
    const p2 = el('p');
    p2.innerHTML =
        '<b>2. En la pantalla:</b> En la columna derecha de Cloudflare, buscá el recuadro <i>Account details</i> (Detalles de la cuenta) donde dice <i>Account ID</i>.';
    box.append(p1, p2);
    sHelp.append(box);
  } else if (actual && actual.id === 'tokenharbor') {
    const box = el('div', undefined, 'cf-help-box');
    box.append(el('h4', '✉️ Verificación de correo en Token Harbor'));
    box.append(el(
        'p',
        'Al registrarte en Token Harbor, te envían un correo de confirmación a tu casilla.'));
    const pWarn = el('p');
    pWarn.style.background = '#fdf3db';
    pWarn.style.border = '1px solid #fae1b3';
    pWarn.style.padding = '8px 10px';
    pWarn.style.borderRadius = '7px';
    pWarn.style.color = '#8c6415';
    pWarn.style.fontSize = '12.5px';
    pWarn.style.lineHeight = '1.45';
    pWarn.innerHTML =
        '<b>⚠️ Muy importante:</b> Tenés que abrir tu casilla de correo y hacer clic en el enlace de verificación antes de generar tu clave de API. Si no confirmás tu cuenta, la clave no funcionará.';
    box.append(pWarn);
    sHelp.append(box);
  } else if (actual && actual.id === 'nvidia') {
    const box = el('div', undefined, 'cf-help-box');
    box.append(el('h4', '📱 Verificación telefónica en NVIDIA'));
    box.append(el(
        'p',
        'Para generar tu clave de API y activar los 1.000 créditos gratuitos, NVIDIA exige verificar un número de teléfono móvil por SMS.'));
    const pWarn = el('p');
    pWarn.style.background = '#fdf3db';
    pWarn.style.border = '1px solid #fae1b3';
    pWarn.style.padding = '8px 10px';
    pWarn.style.borderRadius = '7px';
    pWarn.style.color = '#8c6415';
    pWarn.style.fontSize = '12.5px';
    pWarn.style.lineHeight = '1.45';
    pWarn.innerHTML =
        '<b>⚠️ Atención al agregar cuentas:</b> Cada cuenta de NVIDIA requiere un número de celular único para recibir el código de validación. Tené a mano un número diferente si vas a conectar más de una cuenta.';
    box.append(pWarn);
    sHelp.append(box);
  }
}
function base(step) {
  $('notice').hidden = true;
  paso = step;
  recordar();
  for (let i = 1; i <= 3; i++) {
    $('step-' + i).classList.toggle('active', i === step);
    if (i === step)
      $('step-' + i).setAttribute('aria-current', 'step');
    else
      $('step-' + i).removeAttribute('aria-current');
  }
  $('wizard-main').replaceChildren();
  actualizarAyudaLateral();
  return $('wizard-main');
}
function home() {
  if (ocupado)
    return;
  draft = actual && paso < 3 ? {id : actual.id, paso, editing} : null;
  if ($('key'))
    $('key').value = '';
  $('inicio').hidden = false;
  $('wizard').hidden = true;
  $('notice').hidden = true;
  actual = null;
  actualizarAyudaLateral();
  $('wizard-main').replaceChildren();
  cargar().catch(e => notice(e.message));
}
function copiarTexto(texto) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(texto).catch(() => {});
  } else {
    const ta = document.createElement('textarea');
    ta.value = texto;
    document.body.append(ta);
    ta.select();
    try {
      document.execCommand('copy');
    } catch (e) {
    }
    ta.remove();
  }
}
function urlGoogle(s, email) {
  if (s.id === 'google' && email)
    return `https://accounts.google.com/AccountChooser?Email=${
        encodeURIComponent(email)}&continue=${
        encodeURIComponent('https://aistudio.google.com/apikey')}`;
  return s.logout || s.claves || s.url;
}
function cerrarSesionYEntrar(email) {
  copiarTexto(email);
  if (actual.id === 'google') {
    window.open(urlGoogle(actual, email), '_blank');
    notice(`Copiamos ${
        email} y abrimos Google AI Studio directamente con esa cuenta. Generá tu clave y pegala acá.`);
    editing = '';
    clavePaso(email, true);
    return;
  }
  if (actual.id === 'ollama') {
    window.open(actual.url, '_blank');
    ollamaPaso();
    if ($('email'))
      $('email').value = email;
    notice(`Copiamos ${
        email} al portapapeles. Si tenías otra cuenta en Ollama, cerrá sesión desde tu perfil antes de autorizar.`);
    return;
  }
  if (actual.modo === 'oauth') {
    if (actual.logout)
      window.open(actual.logout, '_blank');
    notice(`Copiamos ${
        email} y cerramos la sesión en OpenRouter. Tocá “Conectar desde el navegador” y elegí tu cuenta de Google.`);
    editing = '';
    clavePaso(email, true);
    return;
  }
  if (actual.logout) {
    window.open(actual.logout, '_blank');
    notice(`Copiamos ${email} y cerramos la sesión anterior en ${
        actual.nombre}. Tocá “Continuar con Google”, elegí ${
        email} y pegá tu clave acá.`);
  } else {
    window.open(actual.claves || actual.url, '_blank');
    notice(`Copiamos ${email} y abrimos ${
        actual
            .nombre}. Si tenías otra cuenta abierta, cerrá sesión desde tu perfil ("Log out") y entrá con Google. Luego pegá tu clave acá.`);
  }
  editing = '';
  clavePaso(email, true);
}
function cuentas() {
  const p = base(1);
  p.append(
      el('h2', 'Tus cuentas de ' + actual.nombre),
      el('p',
         'Revisá el correo asociado a cada cuenta antes de agregar otra. Así evitás repetir cuentas con el mismo correo y aprovechás cada una al máximo.'));
  if (actual.id === 'apinex')
    p.append(note('⚠️ APInex: una sola cuenta por IP es lo más seguro. Si tenés varias cuentas legítimas y APInex permite usarlas, podés configurarlas y rotarlas bajo tu responsabilidad, con moderación. Para recibir los tokens gratuitos del día, abrí https://apinex.bond/airdrop y tocá “Autorizar” en esta cuenta. Sin ese check-in, los modelos free pueden no responder y el servicio puede quedar limitado según el uso.'));
  if (actual.solo_tts)
    p.append(el('div', 'Esta conexión está separada de los servicios generales: se usa únicamente para convertir texto en audio (TTS). No participa en el chat, en la selección de modelos ni en la rotación de cuentas.', 'notice-inline'));
  const usados = actual.cuentas.map(c => (c.email || '').trim().toLowerCase())
                     .filter(Boolean);
  const disponibles =
      emailsConocidos.filter(m => !usados.includes(m.toLowerCase()));
  {
    const poolBox = el('div', undefined, 'email-pool-box');
    const poolHead = el('div', undefined, 'pool-head');
    poolHead.append(
        el('h4', `Pozo de correos (${usados.length} vinculados aquí · ${
                     disponibles.length} sin vincular aquí)`));
    const btnAddPool =
        el('button', '➕ Sumar nuevo correo al pozo', 'pool-btn add-pool');
    btnAddPool.type = 'button';
    btnAddPool.title =
        'Agregar un correo nuevo que no está en ningún servicio para que quede disponible en todos';
    btnAddPool.onclick = () => {
      const m =
          window.prompt('Escribí el nuevo correo para sumar al pozo general:');
      if (m && m.trim()) {
        ejecutar(async () => {
          const r = await api('/api/pozo/agregar', {email : m.trim()});
          await cargar();
          actual = servicios.find(s => s.id === actual.id);
          cuentas();
          notice(`Sumamos ${
              r.email} al pozo. Ya podés usarlo en todos los servicios.`);
        });
      }
    };
    poolHead.append(btnAddPool);
    poolBox.append(poolHead);
    const chips = el('div', undefined, 'pool-chips');
    for (const u of actual.cuentas.filter(c => c.email)) {
      const cChip = el('span', '✓ ' + u.email, 'pool-chip used');
      cChip.title = 'Ya asignado a ' + (u.nombre || u.id);
      chips.append(cChip);
    }
    for (const d of disponibles) {
      const cGroup = el('div', undefined, 'pool-chip-group');
      const cEmail = el('button', d, 'pool-chip-email');
      cEmail.type = 'button';
      cEmail.title = `Tocar para cargar esta cuenta con ${d}`;
      cEmail.onclick = () => {
        copiarTexto(d);
        editing = '';
        if (actual.id === 'ollama')
          ollamaPaso(d);
        else
          clavePaso(d);
        notice(`Elegiste ${
            d}. Copiamos tu correo al portapapeles y preparamos el formulario.`);
      };
      cGroup.append(cEmail);
      const bGoogleText =
          actual.id === 'ollama'
              ? '☁️ Conectar con Ollama ↗'
              : actual.id === 'google'
              ? '⚡ AI Studio con Google ↗'
              : (actual.logout ? '⚡ Cerrar previa y entrar con Google ↗'
                               : '🌐 Abrir panel / Claves ↗');
      const bGoogle =
          el('button', bGoogleText,
             actual.id === 'google' || actual.logout ? 'pool-btn google'
                                                     : 'pool-btn create');
      bGoogle.type = 'button';
      bGoogle.title =
          actual.id === 'google'
              ? `Abrir AI Studio directamente con ${
                    d} usando el selector de Google`
              : (actual.logout
                     ? `Cerrar la sesión de la cuenta previa en ${
                           actual.nombre} y entrar con Google usando ${d}`
                     : `Copiar ${d} y abrir el panel de claves de ${
                           actual.nombre}`);
      bGoogle.onclick = () => cerrarSesionYEntrar(d);
      cGroup.append(bGoogle);
      if (actual.id !== 'ollama') {
        const bKey = el('button', '🔑 Pegar clave', 'pool-btn key');
        bKey.type = 'button';
        bKey.title = `Cargar clave a mano para ${d}`;
        bKey.onclick = () => {
          editing = '';
          clavePaso(d);
        };
        cGroup.append(bKey);
      }
      chips.append(cGroup);
    }
    poolBox.append(chips);
    if (!disponibles.length && !actual.cuentas.filter(c => c.email).length) {
      poolBox.append(el(
          'p',
          'Todavía no hay correos en el pozo. Tocá “➕ Sumar nuevo correo al pozo” para agregar el primero y usarlo en todos los servicios.',
          'pool-empty'));
    } else if (!disponibles.length) {
      poolBox.append(el(
          'p',
          'Todos los correos conocidos ya están asignados en este servicio. Podés sumar otro con el botón de arriba.',
          'pool-empty'));
    }
    p.append(poolBox);
  }
  for (const c of actual.cuentas) {
    const row = el('div', undefined, 'saved-account');
    row.append(el('strong', c.nombre));
    if (c.email) {
      row.append(el('span', '📧 ' + c.email, 'email-badge assigned'));
    } else {
      row.append(el('span', '⚠️ Correo no registrado', 'email-badge missing'));
    }
    if (actual.solo_tts && c.voice_id)
      row.append(el('small', '🔊 Voz configurada: ' + c.voice_id));
    row.append(el('small', (estados[c.estado] || 'Pendiente de comprobar') +
                               (c.fecha ? ' · ' + c.fecha : '')));
    const actions = el('div', undefined, 'actions');
    if (actual.opcional || actual.control_capacidades) {
      const controls = el('div', undefined, 'optional-account-controls');
      const toggle = (field, label, value) => {
        const b = btn(`${value ? '✓ ' : '○ '}${label}`, () => ejecutar(async () => {
          await api('/api/proveedores-opcionales/configurar', {proveedor: actual.id, id: c.id, [field]: !value});
          await cargar();
          actual = servicios.find(s => s.id === actual.id);
          cuentas();
        }), value ? 'secondary' : 'text-btn');
        controls.append(b);
      };
      toggle('habilitado', 'Usable', c.habilitado === true);
      toggle('uso_pago', 'Permitir uso con saldo', c.uso_pago === true);
      toggle('primaria', 'Cuenta primaria', c.primaria === true);
      row.append(controls);
      if (Array.isArray(actual.capacidades_ids) && actual.capacidades_ids.length) {
        const capabilityNames = {
          vision_image: 'Comprensión de imágenes', vision_video: 'Comprensión de video',
          transcription_audio: 'Transcripción de audio', speech_generation: 'Texto a voz',
          transcription_realtime: 'Transcripción en tiempo real', speech_to_speech: 'Voz a voz',
          voice_cloning: 'Clonación de voz', voice_design: 'Diseño y generación de voces',
          audio_isolation: 'Aislamiento de voz', sound_effects: 'Efectos de sonido',
          dubbing: 'Doblaje', forced_alignment: 'Alineación de audio y texto',
          image_generation: 'Imagen desde texto', image_editing: 'Edición de imágenes',
          video_generation_text: 'Video desde texto', video_generation_image: 'Video desde imagen',
          video_editing: 'Edición de video', lip_sync: 'Lip-sync y avatares',
          embeddings: 'Embeddings', parse_documents: 'Lectura de documentos',
          reranking: 'Reordenamiento de resultados', music_generation: 'Generación de música',
          music_editing: 'Edición e inpainting musical', voice_agents: 'Agentes de voz'
        };
        const capabilityControls = el('div', undefined, 'optional-account-controls');
        capabilityControls.append(el('small', 'Capacidades permitidas para esta cuenta:'));
        const activeCapabilities = new Set(c.capacidades_habilitadas || []);
        for (const capability of actual.capacidades_ids) {
          const enabled = activeCapabilities.has(capability);
          const implemented = !Array.isArray(actual.adaptadores_implementados) || actual.adaptadores_implementados.includes(capability);
          const capabilityButton = btn(`${enabled ? '✓ ' : '○ '}${capabilityNames[capability] || capability}${implemented ? '' : ' · pendiente'}`, () => ejecutar(async () => {
            await api('/api/proveedores-opcionales/configurar', {
              proveedor: actual.id, id: c.id, capacidad: capability,
              capacidad_habilitada: !enabled
            });
            await cargar();
            actual = servicios.find(s => s.id === actual.id);
            cuentas();
          }), enabled ? 'secondary' : 'text-btn');
          capabilityButton.disabled = !implemented;
          capabilityControls.append(capabilityButton);
        }
        row.append(capabilityControls);
      }
    }
    actions.append(btn('Comprobar acceso',
                       () => ejecutar(async () => {
                         notice('Comprobando el acceso…');
                         const r =
                             await api('/api/verificar',
                                       {proveedor : actual.id, id : c.id});
                         await cargar();
                         actual = servicios.find(s => s.id === actual.id);
                         cuentas();
                         notice(r.mensaje);
                       }),
                       'secondary'));
    if (actual.id !== 'ollama') {
      if (!c.email) {
        actions.append(btn('Asignar correo', () => {
          editing = c.id;
          clavePaso();
        }, 'primary'));
      }
      actions.append(
          btn(c.email ? 'Editar cuenta' : 'Actualizar clave y correo', () => {
            editing = c.id;
            clavePaso();
          }, 'text-btn'));
    } else if (c.email) {
      actions.append(btn('Volver a autorizar esta cuenta', () => {
        editing = c.id;
        ollamaPaso(c.email);
      }, 'primary'));
    }
    row.append(actions);
    p.append(row);
  }
  p.append(btn('Agregar otra cuenta', () => {
    editing = '';
    cuentaPaso();
  }, 'secondary'));
}
function cuentaPaso() {
  const p = base(1);
  p.append(
      el('h2', 'Primero, tu cuenta'),
      el('p',
         'Entrá al servicio o creá una cuenta. Después volvé a esta pestaña.'));
  const actions = el('div', undefined, 'actions');
  actions.append(link('Tengo cuenta ↗', actual.claves, 'primary'),
                 link('Crear cuenta ↗', actual.url, 'secondary'));
  if (actual.logout)
    actions.append(
        link('🚪 Cerrar sesión previa ↗', actual.logout, 'text-btn'));
  p.append(actions);
  const list = el('ol', undefined, 'instructions');
  actual.pasos.forEach(t => list.append(el('li', t)));
  p.append(list);
  if (actual.nota)
    p.append(note(actual.nota));
  if (actual.solo_tts && emailsConocidos.length) {
    const pool = el('div', undefined, 'email-pool-box');
    pool.append(el('h4', 'Elegí un correo del pozo común'));
    pool.append(el('small', 'Podés reutilizar un correo que ya usás en otros servicios. ElevenLabs lo guarda solo como identificador de la cuenta; la clave queda separada.'));
    const chips = el('div', undefined, 'pool-chips');
    for (const correo of emailsConocidos) {
      const b = el('button', '📧 ' + correo, 'pool-chip avail');
      b.type = 'button';
      b.onclick = () => {
        copiarTexto(correo);
        clavePaso(correo);
        notice(`Elegiste ${correo}. Lo copiamos al portapapeles y lo cargamos en el formulario.`);
      };
      chips.append(b);
    }
    pool.append(chips);
    p.append(pool);
  }
  p.append(note(
      'Antes de continuar, revisá el plan y los precios del servicio. Crear una cuenta no garantiza uso gratuito.'));
  if (actual.id === 'ollama') {
    p.append(btn('Continuar con Ollama Cloud →', ollamaPaso));
    p.append(el('p', '¿Querés usar los modelos de tu computadora?'));
    p.append(btn('Conectar Ollama local',
                 () => ejecutar(async () => {
                   const r = await api('/api/ollama/comprobar', {local : true});
                   if (r.guardada)
                     await terminado(r);
                   else
                     notice(r.mensaje);
                 }),
                 'secondary'));
  } else if (actual.modo === 'oauth') {
    p.append(btn('Conectar desde el navegador →', () => {
      const email = window.prompt('Correo asociado a esta cuenta:', '');
      if (email)
        ejecutar(async () => {
          const r = await api('/api/oauth/iniciar', {email});
          const box = base(2);
          box.append(
              el('h2', 'Autorizá la conexión'),
              el('p',
                 'Revisá los límites en OpenRouter y autorizá. Al terminar, el navegador vuelve a Mis servicios.'),
              link('Abrir autorización de OpenRouter ↗', r.url),
              el('p',
                 'Si no se abre, copiá el enlace y pegalo en otra pestaña.'),
              link('Enlace de autorización', r.url, 'link-fallback'),
              btn('Prefiero pegar una clave', () => clavePaso(), 'text-btn'));
          location.assign(r.url);
        })
    }));
    if (actual.logout)
      p.append(link('Cerrar sesión previa en OpenRouter ↗', actual.logout,
                    'text-btn'));
    p.append(btn('Ya tengo una clave', () => clavePaso(), 'text-btn'));
  } else
    p.append(btn('Ya tengo mi clave →', () => clavePaso()));
}
function campo(p, text, id, type = 'text', placeholder = '') {
  const label = el('label', text);
  label.htmlFor = id;
  const input = el('input');
  input.id = id;
  input.type = type;
  input.placeholder = placeholder;
  input.autocomplete = 'off';
  input.spellcheck = false;
  p.append(label, input);
  return input;
}
function clavePaso(defaultEmail = '', fromRegister = false) {
  const p = base(2);
  const existente = editing && actual.cuentas.find(c => c.id === editing);
  const titulo =
      editing ? (existente?.email
                     ? 'Actualizar cuenta de ' + actual.nombre
                     : 'Asignar correo a ' + (existente?.nombre || 'la cuenta'))
              : 'Pegá tu clave de acceso';
  p.append(
      el('h2', titulo),
      el('p',
         editing
             ? 'Podés cambiar el correo o nombre. Si no cambiás la clave, dejala en blanco para conservar la actual.'
             : 'La clave es el texto que te dio el servicio para conectar aplicaciones. No es tu contraseña.'));
  if (!editing) {
    const banner = el('div', undefined, 'crear-cuenta-banner');
    const bInfo = el('div');
    bInfo.append(
        el('strong', actual.id === 'google'
                         ? 'Acceso rápido con Google AI Studio'
                         : 'Generá tu clave en ' + actual.nombre),
        el('p',
           actual.id === 'google'
               ? 'Podés abrir AI Studio con este correo de Google directamente.'
               : (actual.logout
                      ? 'Podés cerrar la sesión anterior para que “Continuar con Google” te deje elegir este correo.'
                      : 'Abrí el panel oficial para generar tu clave. Si tenías otra cuenta abierta en tu navegador, cerrá sesión desde el menú de perfil (“Log out”) y volvé a entrar con “Continuar con Google”.')));
    const bActions = el('div', undefined, 'actions');
    if (actual.id === 'google') {
      const btnGoogle = btn('⚡ Abrir AI Studio con este Google ↗', () => {
        const m = $('email').value.trim();
        if (m)
          copiarTexto(m);
        window.open(m ? urlGoogle(actual, m) : actual.claves, '_blank');
        notice(`Abrimos Google AI Studio con ${
            m || 'tu cuenta'}. Generá la clave y pegala acá.`);
      }, 'primary');
      btnGoogle.style.fontSize = '12px';
      btnGoogle.style.minHeight = '36px';
      btnGoogle.style.padding = '6px 14px';
      bActions.append(btnGoogle);
    } else {
      if (actual.logout) {
        const btnLogout = btn('⚡ Cerrar previa y entrar con Google ↗', () => {
          const m = $('email').value.trim();
          if (m)
            copiarTexto(m);
          window.open(actual.logout, '_blank');
          notice(m ? `Copiamos ${m} y cerramos la sesión en ${
                         actual.nombre}. Tocá “Continuar con Google”, elegí ${
                         m} y pegá tu clave acá.`
                   : `Cerramos la sesión anterior en ${actual.nombre}.`);
        }, 'primary');
        btnLogout.style.fontSize = '12px';
        btnLogout.style.minHeight = '36px';
        btnLogout.style.padding = '6px 14px';
        bActions.append(btnLogout);
      }
      const btnReg = btn('🌐 Abrir panel de claves ↗', () => {
        const m = $('email').value.trim();
        if (m)
          copiarTexto(m);
        window.open(actual.claves || actual.url, '_blank');
        notice(m ? `Copiamos ${m} y abrimos ${actual.nombre}.`
                 : `Abrimos ${actual.nombre}.`);
      }, actual.logout ? 'secondary' : 'primary');
      btnReg.style.fontSize = '12px';
      btnReg.style.minHeight = '36px';
      btnReg.style.padding = '6px 14px';
      bActions.append(btnReg);
    }
    const btnCop = btn('📋 Copiar correo', () => {
      const m = $('email').value.trim();
      if (m) {
        copiarTexto(m);
        notice(`Correo copiado al portapapeles: ${m}`);
      } else
        notice('Escribí o seleccioná un correo primero.');
    }, 'secondary');
    btnCop.style.fontSize = '12px';
    btnCop.style.minHeight = '36px';
    btnCop.style.padding = '6px 14px';
    bActions.append(btnCop);
    banner.append(bInfo, bActions);
    p.append(banner);
  }
  const form = el('form');
  const email = campo(form, 'Correo asociado a esta cuenta', 'email', 'email',
                      'correo@ejemplo.com');
  email.required = true;
  email.setAttribute('list', 'lista-emails-conocidos');
  if (existente?.email)
    email.value = existente.email;
  else if (defaultEmail)
    email.value = defaultEmail;
  const emailWarn = el('span', '', 'input-warning');
  form.append(emailWarn);
  email.oninput = () => {
    const val = email.value.trim().toLowerCase();
    if (!val) {
      emailWarn.textContent = '';
      return;
    }
    const dup = actual.cuentas.find(
        c => c.id !== editing && (c.email || '').trim().toLowerCase() === val);
    if (dup) {
      emailWarn.textContent =
          `⚠️ Este correo ya está registrado en otra cuenta de ${
              actual.nombre} (${dup.nombre || dup.id}).`;
    } else {
      emailWarn.textContent = '';
    }
  };
  const keyLabel = editing ? 'Clave de acceso (opcional)' : 'Clave de acceso';
  const keyPlace = editing ? 'Dejar en blanco para conservar la clave actual'
                           : 'Pegá aquí la clave completa';
  const key = campo(form, keyLabel, 'key', 'password', keyPlace);
  key.required = !editing;
  key.maxLength = 4096;
  const reveal = el('label', undefined, 'key-reveal');
  const chk = el('input');
  chk.type = 'checkbox';
  chk.onchange = () => key.type = chk.checked ? 'text' : 'password';
  reveal.append(chk, document.createTextNode('Mostrar la clave'));
  form.append(reveal);
  form.append(link('Ir a generar / ver claves en ' + actual.nombre + ' ↗',
                   actual.claves, 'text-btn'));
  if (actual.id === 'cloudflare') {
    const cf = campo(form, 'Identificador de cuenta de Cloudflare (Account ID)',
                     'cf-id', 'text', '32 letras y números (o pegá el enlace)');
    if (!editing)
      cf.required = true;
    cf.maxLength = 150;
    if (existente?.account_id)
      cf.value = existente.account_id;
    cf.oninput = () => {
      const val = cf.value.trim();
      const m = val.match(/[a-fA-F0-9]{32}/);
      if (m && val.length > 32) {
        cf.value = m[0].toLowerCase();
        notice('¡Listo! Extraímos tu Account ID de 32 caracteres.');
      }
    };
    const cfHelp = el('div', undefined, 'cf-field-help');
    const cfLink =
        link('👉 Abrir Workers & Pages para sacar tu Account ID de 32 letras ↗',
             'https://dash.cloudflare.com/?to=/:account/workers-and-pages');
    const cfDesc = el(
        'small',
        'El Account ID son 32 letras y números. Al abrir el enlace de arriba, copialo de la barra de direcciones de tu navegador (está entre dash.cloudflare.com/ y /workers-and-pages) o del recuadro "Account details" a la derecha de Cloudflare. Si pegás la dirección entera acá, sacamos los 32 caracteres automáticamente.');
    cfHelp.append(cfLink, cfDesc);
    form.append(cfHelp);
  }
  if (actual.id === 'elevenlabs') {
    const voice = campo(form, 'ID de voz de ElevenLabs (opcional)', 'voice-id', 'text', 'Por ejemplo: EXAVITQu4vr4xnSDxMaL');
    voice.maxLength = 160;
    if (existente?.voice_id)
      voice.value = existente.voice_id;
    form.append(el('small', 'Solo TTS. Podés dejarlo vacío y configurarlo después en .env como ELEVENLABS_VOICE_ID.'));
  }
  const name = campo(form, 'Nombre para reconocer esta cuenta (opcional)',
                     'name', 'text', 'Por ejemplo: Mi cuenta personal');
  name.maxLength = 80;
  if (existente?.nombre)
    name.value = existente.nombre;
  form.append(el('small', 'Solo se usa dentro de Núcleo IA.'));
  const feedback = el('div');
  feedback.id = 'form-feedback';
  form.append(feedback);
  const actions = el('div', undefined, 'actions');
  const submit =
      btn(editing ? 'Guardar cambios →' : 'Comprobar y guardar →', null);
  submit.type = 'submit';
  actions.append(
      submit,
      btn('Volver', actual.cuentas.length ? cuentas : cuentaPaso, 'text-btn'));
  form.append(actions);
  form.onsubmit = e => {
    e.preventDefault();
    guardar(false);
  };
  p.append(
      form,
      el('small',
         'La comprobación consulta el acceso o el catálogo; no genera conversaciones ni prueba modelos pagos.'));
  email.focus();
}

function guardar(pending) {
  ejecutar(async () => {
    const feedback = $('form-feedback');
    feedback.replaceChildren(
        note('Guardando datos. Puede tardar unos segundos…'));
    const body = {
      proveedor : actual.id,
      clave : $('key') ? $('key').value : '',
      email : $('email').value,
      nombre : $('name').value,
      cf_id : $('cf-id')?.value || '',
      voice_id : $('voice-id')?.value || '',
      id : editing,
      guardar_pendiente : pending
    };
    const r = await api('/api/conectar', body);
    if (r.guardada) {
      if ($('key'))
        $('key').value = '';
      await terminado(r);
    } else {
      feedback.replaceChildren(note(r.mensaje));
      if (!['clave_rechazada', 'sin_permiso'].includes(r.estado))
        feedback.append(
            btn('Guardar como pendiente', () => guardar(true), 'secondary'));
    }
  });
}
function ollamaPaso(defaultEmail = '') {
  const p = base(2);
  p.append(
      el('h2', 'Vinculá Ollama Cloud'),
      el('p',
         'Usá el mismo correo con el que vas a iniciar sesión en Ollama.'));
  const form = el('form');
  const email = campo(form, 'Correo de tu cuenta de Ollama', 'email', 'email',
                      'Tu correo');
  email.required = true;
  email.setAttribute('list', 'lista-emails-conocidos');
  email.value = defaultEmail;
  const prepare = btn('Preparar conexión →', null);
  prepare.type = 'submit';
  const actions = el('div', undefined, 'actions');
  actions.append(prepare, link('Instalar Ollama ↗',
                               'https://ollama.com/download', 'secondary'));
  if (actual.logout)
    actions.append(link('🚪 Cerrar sesión previa en ollama.com ↗',
                        actual.logout, 'text-btn'));
  form.append(actions);
  const box = el('div');
  form.onsubmit = e => {
    e.preventDefault();
    ejecutar(async () => {
      const r = await api('/api/ollama/preparar',
                          {email : email.value, id : editing || ''});
      box.replaceChildren(
          note(
              'Conexión preparada. Abrí la autorización con el correo que indicaste.'),
          link('Abrir autorización de Ollama ↗', r.url),
          el('p', 'Después de elegir “Authorize Device”, volvé acá.'),
          btn('Ya autoricé: comprobar', () => ejecutar(async () => {
                                          const r = await api(
                                              '/api/ollama/comprobar', {});
                                          if (r.guardada)
                                            await terminado(r);
                                          else
                                            notice(r.mensaje);
                                        })),
          link('Abrir el enlace nuevamente', r.url, 'link-fallback'));
    });
  };
  p.append(form, box);
  p.append(btn('Ya autoricé una conexión pendiente',
               () => ejecutar(async () => {
                 const r = await api('/api/ollama/comprobar', {});
                 if (r.guardada)
                   await terminado(r);
                 else
                   notice(r.mensaje);
               }),
               'text-btn'));
}

async function terminado(r) {
  await cargar();
  sessionStorage.removeItem('nucleo-draft');
  const p = base(3);
  sessionStorage.removeItem('nucleo-draft');
  p.append(
      el('div', r.verificada ? '✓' : '…', 'result-mark'),
      el('h2', r.verificada ? 'Tu conexión quedó guardada'
                            : 'Cuenta guardada como pendiente'),
      note(r.mensaje, r.verificada),
      el('p',
         'Aplicá las conexiones para que Núcleo IA cargue las cuentas guardadas. La prueba de un modelo y su cuota se realiza al usarlo.'));
  const actions = el('div', undefined, 'actions');
  actions.append(btn('Aplicar conexiones', aplicar),
                 btn('Volver a Mis servicios', home, 'secondary'));
  p.append(actions);
}
function aplicar() {
  ejecutar(async () => {
    notice('Aplicando conexiones. Si Núcleo IA está detenido, lo iniciamos…');
    const r = await api('/api/aplicar', {});
    notice(r.mensaje);
  });
}
function ayuda() {
  const box = $('help-content');
  box.replaceChildren();
  box.append(
      el('p',
         '1. Abrí la página del servicio. Completá el registro o iniciá sesión allí.'),
      el('p',
         '2. Volvé a esta pestaña para continuar. Si pide una clave, copiala completa y pegala en el campo indicado.'),
      el('p',
         '3. Tocá “Comprobar y guardar”. Si algo falta, el asistente te explica cómo seguir.'));
  box.append(note(
      '⚠️ Cuidado con la cuenta activa: Si tenías abierta una sesión con otro correo en ese servicio, asegurate de cerrarla (Log out) y verificar que iniciaste con el correo exacto de la cuenta que querés agregar antes de generar o copiar la clave.'));
  if (actual) {
    const list = el('ol');
    actual.pasos.forEach(t => list.append(el('li', t)));
    box.append(el('h3', 'Ayuda para ' + actual.nombre), list,
               link('Abrir guía oficial ↗', actual.ayuda, 'secondary'));
  }
  box.append(
      el('p',
         '¿La página está en inglés? “Sign up” significa crear cuenta, “Sign in” iniciar sesión y “API key” clave de acceso.'),
      el('p',
         'Si no se abre la otra pestaña, permití la apertura en tu navegador o copiá el enlace con el botón derecho.'),
      el('p',
         'Podés continuar después desde el acceso directo. Se recuerda el servicio elegido; nunca se guarda una clave sin que toques Guardar.'));
  $('help-dialog').showModal();
}
function actualizarOpcionesPerfil() {
  const profesional = $('profile-select').value === 'profesional';
  $('professional-options').hidden = !profesional;
  $('network-options').hidden = !profesional || !$('profile-network').checked;
}
function abrirPerfil() {
  if (!perfilActual)
    return;
  $('profile-select').value = perfilActual.perfil;
  $('profile-network').checked = perfilActual.acceso_red;
  $('profile-hosts').value = (perfilActual.hosts_permitidos || []).join(', ');
  $('profile-origins').value = (perfilActual.origenes || []).join(', ');
  const warnings = $('profile-warnings');
  warnings.replaceChildren();
  for (const aviso of perfilActual.avisos || [])
    warnings.append(note(aviso));
  actualizarOpcionesPerfil();
  $('profile-dialog').showModal();
}
function guardarPerfil() {
  ejecutar(async () => {
    const r = await api('/api/perfil/aplicar', {
      perfil: $('profile-select').value,
      acceso_red: $('profile-network').checked,
      hosts_permitidos: $('profile-hosts').value,
      origenes: $('profile-origins').value
    });
    perfilActual = r;
    $('profile-dialog').close();
    await cargarPerfil();
    notice(r.mensaje);
  });
}
$('back').onclick = home;
$('brand').onclick = e => {
  e.preventDefault();
  home();
};
$('later').onclick = () => {
  home();
  notice(
      'Podés volver cuando quieras. Las claves que no guardaste se borraron del formulario.');
};
$('help-general').onclick = ayuda;
$('help-service').onclick = ayuda;
$('close-help').onclick = () => $('help-dialog').close();
$('profile-open').onclick = abrirPerfil;
$('profile-close').onclick = () => $('profile-dialog').close();
$('profile-cancel').onclick = () => $('profile-dialog').close();
$('profile-select').onchange = actualizarOpcionesPerfil;
$('profile-network').onchange = actualizarOpcionesPerfil;
$('profile-save').onclick = guardarPerfil;
$('apply-home').onclick = aplicar;
ejecutar(async () => {
  await cargar();
  if (callback) {
    actual = servicios.find(s => s.id === callback);
    abrirServicio(callback);
    notice(
        'La autorización terminó. Revisá el estado de tu cuenta y aplicá las conexiones.');
  } else if (draft && servicios.some(s => s.id === draft.id)) {
    const resume = btn('Continuar conexión de ' +
                           servicios.find(s => s.id === draft.id).nombre,
                       () => {
                         abrirServicio(draft.id, true);
                         editing = draft.editing || '';
                         if (draft.paso === 2) {
                           if (actual.id === 'ollama')
                             ollamaPaso();
                           else if (actual.modo !== 'oauth')
                             clavePaso();
                         }
                       },
                       'secondary');
    $('inicio').insertBefore(resume, $('cards'));
  }
});
