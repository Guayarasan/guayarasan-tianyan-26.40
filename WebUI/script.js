/**
 * TitanEye Console Script
 * Implementado con JS nativo (ES6+), sin dependencias
 */

// --- Gestión de estado global ---
const state = {
    token: localStorage.getItem('ty_secret') || '',
    apiUrl: localStorage.getItem('ty_api_base') || 'http://127.0.0.1:8098',
    currentPage: 1,
    totalPages: 1,
    totalRecords: 0,
    pageSize: 100,
    logs: [],
    currentLang: localStorage.getItem('ty_lang') || 'zh_CN',
    langData: {}
};

// --- Selectores rápidos del DOM ---
const $ = (selector) => document.querySelector(selector);
const show = (el) => el.style.display = 'flex';
const hide = (el) => el.style.display = 'none';

// --- Funciones utilitarias de UI ---

function toast(msg, type = 'success') {
    const container = $('#toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `<span>${msg}</span><span style="cursor:pointer;margin-left:10px" onclick="this.parentElement.remove()">✕</span>`;
    container.appendChild(el);
    setTimeout(() => {
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 300);
    }, 3000);
}

function setLoading(isLoading, text = 'Cargando...') {
    const overlay = $('#loading-overlay');
    $('#loading-text').innerText = text;
    overlay.style.display = isLoading ? 'flex' : 'none';
}

// --- Funciones de manejo de idioma ---

async function loadAvailableLanguages() {
    try {
        const response = await fetch(`${state.apiUrl}/api/languages`);
        const data = await response.json();
        return data.languages;
    } catch (error) {
        console.error("Failed to load languages:", error);
        return ['en_US', 'zh_CN']; // Lista de idiomas por defecto
    }
}

async function loadLanguage(langCode) {
    try {
        const response = await fetch(`${state.apiUrl}/api/language/${langCode}`);
        if (!response.ok) {
            throw new Error(`Failed to load language: ${langCode}`);
        }
        const data = await response.json();
        state.langData = data;
        state.currentLang = langCode;
        localStorage.setItem('ty_lang', langCode);
        applyTranslations();

        // Actualizar el valor seleccionado de los selectores de idioma
        updateLanguageSelectors();

        // Establecer el atributo de idioma del documento, afecta a componentes del navegador como el selector de fecha
        document.documentElement.lang = langCode;

        return true;
    } catch (error) {
        console.error("Failed to load language file:", error);
        // Intentar cargar el idioma por defecto
        if (langCode !== 'en_US') {
            return await loadLanguage('en_US');
        }
        return false;
    }
}

function updateLanguageSelectors() {
    // Actualizar el valor de todos los selectores de idioma
    const selectors = ['#language-select-login', '#language-select-main'];
    selectors.forEach(selector => {
        const el = $(selector);
        if (el) {
            el.value = state.currentLang;
        }
    });
}

function applyTranslations() {
    // Traducir todos los elementos con atributo data-i18n
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        if (state.langData[key]) {
            // Caso especial: para elementos select, solo actualizar el texto de las opciones sin cambiar el valor
            if (element.tagName === 'SELECT') {
                // Guardar el valor actualmente seleccionado
                const currentValue = element.value;
                // Actualizar el texto de todas las opciones
                Array.from(element.options).forEach(option => {
                    const optionKey = option.getAttribute('data-i18n');
                    if (optionKey && state.langData[optionKey]) {
                        option.textContent = state.langData[optionKey];
                    }
                });
                // Restaurar el valor seleccionado
                element.value = currentValue;
            } else {
                // Para el resto de elementos, actualizar el texto directamente
                element.textContent = state.langData[key];
            }
        }
    });

    // Traducir el placeholder
    document.querySelectorAll('[data-placeholder-i18n]').forEach(element => {
        const key = element.getAttribute('data-placeholder-i18n');
        if (state.langData[key]) {
            element.placeholder = state.langData[key];
        }
    });

    // Actualizar el título de la página
    if (state.langData['page_title']) {
        document.title = state.langData['page_title'];
    }

    // Actualizar la información de paginación
    updatePageInfo();
}

function updatePageInfo() {
    if (!state.totalRecords && state.totalRecords !== 0) return;

    const start = (state.currentPage - 1) * state.pageSize + 1;
    const end = Math.min(state.currentPage * state.pageSize, state.totalRecords);
    const displayEnd = state.totalRecords === 0 ? 0 : end;
    const displayStart = state.totalRecords === 0 ? 0 : start;

    const pageInfoText = state.langData['page_info'] || 'Mostrando {start} - {end} de {total} registros';
    const formattedText = pageInfoText
        .replace('{start}', displayStart.toLocaleString())
        .replace('{end}', displayEnd.toLocaleString())
        .replace('{total}', state.totalRecords.toLocaleString());

    $('#page-info').innerText = formattedText;
    $('#page-total').innerText = state.totalPages;
}

// --- Núcleo de comunicación con la API ---

async function apiCall(endpoint, params = {}) {
    const url = new URL(`${state.apiUrl}/api${endpoint}`);
    if (params) {
        Object.keys(params).forEach(key => {
            if (params[key] !== null && params[key] !== '' && params[key] !== undefined) {
                url.searchParams.append(key, params[key]);
            }
        });
    }

    try {
        const response = await fetch(url, {
            headers: {
                'X-Secret': state.token,
                'X-Lang': state.currentLang
            }
        });

        if (response.status === 403) {
            toast(state.langData['auth_failed'] || 'Clave incorrecta o sesión no iniciada', 'error');
            handleLogout();
            throw new Error('Auth failed');
        }

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || (state.langData['request_failed'] || 'Solicitud fallida'));
        }

        return await response.json();
    } catch (error) {
        console.error("API Error:", error);
        if (error.message !== 'Auth failed') {
            toast(error.message, 'error');
        }
        throw error;
    }
}

// --- Lógica de negocio ---

async function handleLogin() {
    const urlRaw = $('#api-url').value;
    const url = urlRaw.replace(/\/$/, '');
    const secret = $('#api-secret').value;

    if (!url || !secret) {
        toast(state.langData['fill_all_info'] || 'Por favor completa toda la información', 'error');
        return;
    }

    state.apiUrl = url;
    state.token = secret;
    setLoading(true, state.langData['connecting'] || 'Conectando al servidor...');

    try {
        const stats = await apiCall('/stats');
        localStorage.setItem('ty_api_base', state.apiUrl);
        localStorage.setItem('ty_secret', state.token);

        $('#login-view').style.display = 'none';
        $('#main-view').style.display = 'flex';
        updateStatsUI(stats);
        toast(state.langData['login_success'] || 'Inicio de sesión exitoso');

        // Tras iniciar sesión, intentar cargar los datos una vez
        fetchLogs(1);

    } catch (e) {
        console.error("Login error:", e);
    } finally {
        setLoading(false);
    }
}

function handleLogout() {
    localStorage.removeItem('ty_secret');
    state.token = '';
    $('#main-view').style.display = 'none';
    $('#login-view').style.display = 'flex';
}

async function fetchStats() {
    setLoading(true, state.langData['refreshing_stats'] || 'Actualizando estadísticas...');
    try {
        const data = await apiCall('/stats');
        updateStatsUI(data);
        toast(state.langData['stats_refreshed'] || 'Estadísticas actualizadas');
    } catch(e) {
        console.error("Failed to fetch stats:", e);
    } finally {
        setLoading(false);
    }
}

function updateStatsUI(data) {
    $('#stat-total').innerText = data.total_logs ? data.total_logs.toLocaleString() : '--';
    $('#stat-size').innerText = data.db_size || '--';
    if (data.query_time_ms) {
        $('#stat-time').innerText = data.query_time_ms + ' ms';
    }
}

function getQueryParams() {
    const startVal = $('#filter-start').value;
    const endVal = $('#filter-end').value;
    const startTime = startVal ? Math.floor(new Date(startVal).getTime() / 1000) : null;
    const endTime = endVal ? Math.floor(new Date(endVal).getTime() / 1000) : null;

    const x = $('#coord-x').value;
    const y = $('#coord-y').value;
    const z = $('#coord-z').value;
    const r = $('#coord-r').value;
    let hasCoords = (x!=='' && y!=='' && z!=='' && r!=='');

    let dim = $('#coord-dim').value;
    if (dim === 'custom') dim = $('#coord-dim-custom').value;
    if (dim === 'all') dim = null;

    return {
        page_size: parseInt($('#page-size').value),
        filter_type: $('#filter-type').value,
        filter_value: $('#filter-value').value,
        start_time: startTime,
        end_time: endTime,
        center_x: hasCoords ? parseFloat(x) : null,
        center_y: hasCoords ? parseFloat(y) : null,
        center_z: hasCoords ? parseFloat(z) : null,
        radius: hasCoords ? parseFloat(r) : null,
        dimension: dim
    };
}

async function fetchLogs(page) {
    setLoading(true, state.langData['querying_data'] || 'Consultando datos...');
    state.currentPage = page;
    const params = { ...getQueryParams(), page: page };

    try {
        const res = await apiCall('/logs', params);
        state.logs = res.data;
        state.totalRecords = res.total;
        state.totalPages = res.total_pages;

        if(res.query_time_ms) $('#stat-time').innerText = res.query_time_ms + ' ms';

        renderTable(res.data, params.center_x !== null);
        renderPagination();

        if (res.data.length === 0) {
            $('#empty-state').style.display = 'block';
            $('#logs-table').style.display = 'none';
        } else {
            $('#empty-state').style.display = 'none';
            $('#logs-table').style.display = 'table';
        }

    } catch (e) {
        console.error("Failed to fetch logs:", e);
    } finally {
        setLoading(false);
    }
}

function renderTable(logs, showDistance) {
    const tbody = $('#logs-body');
    tbody.innerHTML = '';
    const thDist = $('#th-dist');
    thDist.style.display = showDistance ? 'table-cell' : 'none';

    logs.forEach(log => {
        const tr = document.createElement('tr');
        const timeStr = new Date(log.time * 1000).toLocaleString(state.currentLang.replace('_', '-'));
        const distStr = log.distance ? `${parseFloat(log.distance).toFixed(1)}m` : '-';
        const distCell = showDistance ? `<td class="dist-cell">${distStr}</td>` : '';

        const sourceHtml = `
            <div class="cell-content">${log.name || '-'}</div>
            <div class="sub-text">${log.id || ''}</div>
        `;
        const targetHtml = `
            <div class="cell-content">${log.obj_name || '-'}</div>
            <div class="sub-text">${log.obj_id || ''}</div>
        `;

        tr.innerHTML = `
            <td style="color:#666;">${timeStr}</td>
            <td>${sourceHtml}</td>
            <td><span class="tag tag-action">${log.type}</span></td>
            <td>${targetHtml}</td>
            <td>
                <div class="coord-cell" style="display:flex;align-items:center;gap:4px;">
                    <span>${log.pos_x.toFixed(1)}, ${log.pos_y.toFixed(1)}, ${log.pos_z.toFixed(1)}</span>
                    <span class="tag tag-world">${log.world}</span>
                </div>
            </td>
            ${distCell}
            <td class="data-json">${log.data || ''}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderPagination() {
    $('#page-curr').innerText = state.currentPage;
    $('#page-total').innerText = state.totalPages;
    $('#btn-prev').disabled = state.currentPage <= 1;
    $('#btn-next').disabled = state.currentPage >= state.totalPages;

    // Restablecer el campo de ir a página
    $('#jump-page-input').value = '';

    updatePageInfo();
}

function changePage(delta) {
    const newPage = state.currentPage + delta;
    if (newPage >= 1 && newPage <= state.totalPages) fetchLogs(newPage);
}

function jumpToPage() {
    const input = $('#jump-page-input');
    const pageStr = input.value.trim();

    if (!pageStr) {
        toast(state.langData['enter_page_number'] || 'Por favor ingresa un número de página', 'error');
        input.focus();
        return;
    }

    const page = parseInt(pageStr);

    if (isNaN(page) || page < 1) {
        toast(state.langData['invalid_page_number'] || 'Por favor ingresa un número de página válido', 'error');
        input.value = '';
        input.focus();
        return;
    }

    if (page > state.totalPages) {
        toast((state.langData['page_exceeds_max'] || 'El número de página no puede superar el máximo de {max} páginas').replace('{max}', state.totalPages), 'error');
        input.value = '';
        input.focus();
        return;
    }

    fetchLogs(page);
}

function resetFilters() {
    $('#filter-start').value = '';
    $('#filter-end').value = '';
    $('#filter-type').value = '';
    $('#filter-value').value = '';
    $('#coord-x').value = '';
    $('#coord-y').value = '';
    $('#coord-z').value = '';
    $('#coord-r').value = '10';
    $('#coord-dim').value = 'all';
    $('#coord-dim-custom').style.display = 'none';
    $('#coord-dim-custom').value = '';
    toast(state.langData['filters_reset'] || 'Filtros restablecidos');
}

async function showDbInfo() {
    setLoading(true);
    try {
        const [info, stats] = await Promise.all([
            apiCall('/db_info'),
            apiCall('/stats')
        ]);

        const msg = `
${state.langData['db_size'] || 'Tamaño de la base de datos'}: ${stats.db_size}
-------------------------
${state.langData['table_count'] || 'Cantidad de tablas'}: ${info.tables?.length || 0}
${state.langData['index_count'] || 'Cantidad de índices'}: ${info.indexes?.length || 0}
${state.langData['column_count'] || 'Cantidad de columnas'}: ${info.columns?.length || 0}
${state.langData['total_rows'] || 'Filas totales (estimado)'}: ${info.total_rows || 0}
        `;
        alert(msg);
    } catch(e) {
        console.error("Failed to fetch DB info:", e);
    } finally {
        setLoading(false);
    }
}

async function exportData() {
    if (state.totalRecords === 0) {
        toast(state.langData['no_data_to_export'] || 'No hay datos para exportar', 'error');
        return;
    }

    if (!confirm(state.langData['confirm_export'] || '¿Seguro que deseas exportar los datos con los filtros actuales?')) return;

    setLoading(true, state.langData['generating_csv'] || 'Generando CSV...');
    const params = { ...getQueryParams(), start_page: 1, end_page: 500 };

    try {
        const res = await apiCall('/export', params);
        if (res.data && res.data.length > 0) {
            const headers = ["Time", "SourceID", "SourceName", "Type", "TargetID", "TargetName", "World", "X", "Y", "Z", "Data"];
            const rows = res.data.map(r => [
                new Date(r.time * 1000).toLocaleString(state.currentLang.replace('_', '-')),
                r.id, r.name, r.type, r.obj_id, r.obj_name, r.world,
                r.pos_x, r.pos_y, r.pos_z,
                `"${(r.data||'').replace(/"/g, '""')}"`
            ]);

            const csvContent = "\ufeff" + [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = `tianyan_export_${new Date().getTime()}.csv`;
            link.click();
            toast((state.langData['export_success'] || 'Se exportaron {count} registros correctamente').replace('{count}', res.data.length.toLocaleString()));
        } else {
            toast(state.langData['no_data_returned'] || 'El servidor no devolvió datos', 'error');
        }
    } catch (e) {
        console.error("Export error:", e);
    } finally {
        setLoading(false);
    }
}

// Inicializar el selector de idioma
async function initLanguageSelectors(languages) {
    const selectLogin = $('#language-select-login');
    const selectMain = $('#language-select-main');

    if (!selectLogin || !selectMain) return;

    // Vaciar las opciones existentes
    selectLogin.innerHTML = '';
    selectMain.innerHTML = '';

    // Agregar las opciones de idioma
    languages.forEach(lang => {
        const optionLogin = document.createElement('option');
        optionLogin.value = lang;

        // Mostrar un nombre amigable según el código de idioma
        let displayName = lang;
        if (lang === 'en_US') displayName = 'English';
        if (lang === 'zh_CN') displayName = '中文';
        if (lang === 'ru_RU') displayName = 'Русский';
        if (lang === 'es_ES') displayName = 'Español';

        optionLogin.textContent = displayName;
        selectLogin.appendChild(optionLogin);

        const optionMain = optionLogin.cloneNode(true);
        selectMain.appendChild(optionMain);
    });

    // Establecer el idioma actual
    updateLanguageSelectors();

    // Agregar los listeners de eventos
    selectLogin.addEventListener('change', async (e) => {
        await loadLanguage(e.target.value);
    });

    selectMain.addEventListener('change', async (e) => {
        await loadLanguage(e.target.value);
    });
}

// Función de inicio de sesión automático
async function autoLogin() {
    if (!state.token) return false;

    setLoading(true, state.langData['connecting'] || 'Conectando al servidor...');
    try {
        const stats = await apiCall('/stats');

        $('#login-view').style.display = 'none';
        $('#main-view').style.display = 'flex';
        updateStatsUI(stats);

        // Cargar datos
        fetchLogs(1);
        return true;
    } catch (e) {
        console.error("Auto login failed:", e);
        // Si el inicio de sesión automático falla, borrar el token
        localStorage.removeItem('ty_secret');
        state.token = '';
        return false;
    } finally {
        setLoading(false);
    }
}

// Función de inicialización
async function init() {
    // Establecer el estado de visualización inicial
    $('#login-view').style.display = 'flex';
    $('#main-view').style.display = 'none';

    // Establecer los valores del formulario
    $('#api-url').value = state.apiUrl;
    $('#api-secret').value = state.token;

    // Obtener la lista de idiomas disponibles
    const languages = await loadAvailableLanguages();
    await initLanguageSelectors(languages);

    // Cargar el idioma actual
    await loadLanguage(state.currentLang);

    // Intentar inicio de sesión automático
    if (state.token) {
        await autoLogin();
    }

    // Establecer los listeners de eventos
    $('#btn-login').addEventListener('click', handleLogin);
    $('#btn-logout').addEventListener('click', handleLogout);
    $('#btn-refresh-stats').addEventListener('click', fetchStats);
    $('#btn-search').addEventListener('click', () => fetchLogs(1));
    $('#btn-reset').addEventListener('click', resetFilters);
    $('#btn-export').addEventListener('click', exportData);
    $('#btn-prev').addEventListener('click', () => changePage(-1));
    $('#btn-next').addEventListener('click', () => changePage(1));
    $('#btn-db-info').addEventListener('click', showDbInfo);
    $('#btn-jump-page').addEventListener('click', jumpToPage);

    // El campo de ir a página admite la tecla Enter
    $('#jump-page-input').addEventListener('keyup', (e) => {
        if (e.key === 'Enter') jumpToPage();
    });

    $('#filter-value').addEventListener('keyup', (e) => {
        if (e.key === 'Enter') fetchLogs(1);
    });

    $('#page-size').addEventListener('change', () => {
        state.pageSize = parseInt($('#page-size').value);
        fetchLogs(1);
    });

    $('#coord-dim').addEventListener('change', (e) => {
        $('#coord-dim-custom').style.display = e.target.value === 'custom' ? 'block' : 'none';
    });
}

// Inicializar cuando la página termine de cargar
document.addEventListener('DOMContentLoaded', init);