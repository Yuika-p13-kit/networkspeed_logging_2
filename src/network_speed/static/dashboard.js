/**
 * Network Speed Dashboard - API Client & UI Controller
 * 
 * Handles:
 * - Fetching latest, history, and stats from API endpoints
 * - Updating UI with data
 * - Auto-refresh for latest values (10 seconds)
 * - Event handling for search, filters, and pagination
 * - Error handling and user feedback
 */

// ============================================================================
// State Management
// ============================================================================

const DashboardState = {
    currentLimit: 100,
    currentOffset: 0,
    currentFrom: null,
    currentTo: null,
    totalRecords: 0,
    autoRefreshInterval: null,
};

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch latest measurement from /api/dashboard/latest
 * @returns {Promise<Object>} Latest measurement record
 */
async function fetchLatest() {
    try {
        const response = await fetch('/api/dashboard/latest');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching latest:', error);
        throw error;
    }
}

/**
 * Fetch history records from /api/dashboard/history
 * @param {Object} options - Query options
 * @param {string} options.from - Start datetime (ISO format)
 * @param {string} options.to - End datetime (ISO format)
 * @param {number} options.limit - Max records to return
 * @param {number} options.offset - Record offset for pagination
 * @returns {Promise<Object>} History response with records array
 */
async function fetchHistory(options = {}) {
    try {
        const params = new URLSearchParams();
        
        if (options.from) params.append('from', options.from);
        if (options.to) params.append('to', options.to);
        if (options.limit) params.append('limit', options.limit);
        if (options.offset !== undefined) params.append('offset', options.offset);

        const url = `/api/dashboard/history?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching history:', error);
        throw error;
    }
}

/**
 * Fetch statistics from /api/dashboard/stats
 * @param {Object} options - Query options
 * @param {string} options.from - Start datetime (ISO format)
 * @param {string} options.to - End datetime (ISO format)
 * @returns {Promise<Object>} Statistics object with aggregates
 */
async function fetchStats(options = {}) {
    try {
        const params = new URLSearchParams();
        
        if (options.from) params.append('from', options.from);
        if (options.to) params.append('to', options.to);

        const url = `/api/dashboard/stats?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching stats:', error);
        throw error;
    }
}

// ============================================================================
// UI Update Functions
// ============================================================================

/**
 * Update latest value display panel
 * @param {Object} data - DashboardRecord from /api/dashboard/latest
 */
function updateLatestDisplay(data) {
    try {
        // Hide loading spinner, show content
        document.getElementById('latest-loading').style.display = 'none';
        document.getElementById('latest-content').style.display = 'block';

        // Update timestamp
        const timestamp = new Date(data.timestamp);
        document.getElementById('latest-timestamp').textContent = formatTimestamp(timestamp);

        // Update download/upload speeds
        document.getElementById('latest-download').innerHTML = 
            `<span class="fs-5 fw-bold text-primary">${formatNumber(data.download_speed_mbps)}</span> <small class="text-muted">Mbps</small>`;
        document.getElementById('latest-upload').innerHTML = 
            `<span class="fs-5 fw-bold text-success">${formatNumber(data.upload_speed_mbps)}</span> <small class="text-muted">Mbps</small>`;

        // Update device
        document.getElementById('latest-device').textContent = data.device || 'Unknown';

        // Update status badge
        const statusElement = document.getElementById('latest-status');
        const statusClass = data.status === 'success' ? 'bg-success' : 'bg-danger';
        const statusText = data.status === 'success' ? 'Success' : (data.error_summary || data.status);
        statusElement.innerHTML = `<span class="badge ${statusClass}">${statusText}</span>`;

        // Update footer timestamp
        updateFooterTime();

        // Clear error alert
        hideErrorAlert();
    } catch (error) {
        console.error('Error updating latest display:', error);
        showErrorAlert('Failed to parse latest data');
    }
}

/**
 * Update history table with records
 * @param {Array<Object>} records - Array of DashboardRecord
 */
function updateHistoryTable(records) {
    const tbody = document.getElementById('history-table-body');
    tbody.innerHTML = ''; // Clear existing rows

    if (records.length === 0) {
        document.getElementById('history-content').style.display = 'none';
        document.getElementById('no-data-message').style.display = 'block';
        document.getElementById('pagination-info').style.display = 'none';
        return;
    }

    // Show table, hide "no data" message
    document.getElementById('history-content').style.display = 'block';
    document.getElementById('no-data-message').style.display = 'none';

    // Populate table rows
    records.forEach(record => {
        const row = document.createElement('tr');
        
        const timestamp = new Date(record.timestamp);
        const statusClass = record.status === 'success' ? 'success' : 'danger';
        const statusText = record.status === 'success' ? 'Success' : record.error_summary || record.status;

        row.innerHTML = `
            <td><small>${formatTimestamp(timestamp)}</small></td>
            <td><strong>${formatNumber(record.download_speed_mbps)}</strong></td>
            <td><strong>${formatNumber(record.upload_speed_mbps)}</strong></td>
            <td><small>${record.device}</small></td>
            <td><span class="badge bg-${statusClass}">${statusText}</span></td>
        `;
        
        tbody.appendChild(row);
    });

    // Show pagination info
    updatePaginationInfo();
}

/**
 * Update statistics display panel
 * @param {Object} stats - StatsResponse object
 */
function updateStats(stats) {
    try {
        document.getElementById('stats-loading').style.display = 'none';
        document.getElementById('stats-content').style.display = 'block';

        // Format values or show "-" if null
        const formatStat = (value) => value !== null ? formatNumber(value) : '-';

        document.getElementById('stats-count').textContent = stats.count;
        document.getElementById('stats-download-avg').textContent = formatStat(stats.avg_download_mbps);
        document.getElementById('stats-download-max').textContent = formatStat(stats.max_download_mbps);
        document.getElementById('stats-download-min').textContent = formatStat(stats.min_download_mbps);
        document.getElementById('stats-upload-avg').textContent = formatStat(stats.avg_upload_mbps);
        document.getElementById('stats-upload-max').textContent = formatStat(stats.max_upload_mbps);
        document.getElementById('stats-upload-min').textContent = formatStat(stats.min_upload_mbps);

        hideErrorAlert();
    } catch (error) {
        console.error('Error updating stats display:', error);
        showErrorAlert('Failed to parse stats data');
    }
}

// ============================================================================
// Pagination & Info Display
// ============================================================================

/**
 * Update pagination info display
 */
function updatePaginationInfo() {
    const { currentOffset, currentLimit, totalRecords } = DashboardState;
    
    const start = currentOffset + 1;
    const end = Math.min(currentOffset + currentLimit, totalRecords);
    
    document.getElementById('pagination-start').textContent = start;
    document.getElementById('pagination-end').textContent = end;
    document.getElementById('pagination-total').textContent = totalRecords;
    document.getElementById('page-info').textContent = 
        `Page ${Math.floor(currentOffset / currentLimit) + 1}`;
    
    document.getElementById('pagination-info').style.display = 'block';
}

/**
 * Update page number info
 */
function updatePageInfo() {
    const { currentOffset, currentLimit } = DashboardState;
    const pageNum = Math.floor(currentOffset / currentLimit) + 1;
    document.getElementById('page-info').textContent = `Page ${pageNum}`;
}

/**
 * Update footer with current time
 */
function updateFooterTime() {
    const now = new Date();
    document.getElementById('footer-update-time').textContent = formatTimestamp(now);
}

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Show error alert with message
 * @param {string} message - Error message to display
 */
function showErrorAlert(message) {
    const alertDiv = document.getElementById('error-alert');
    document.getElementById('error-message').textContent = message;
    alertDiv.style.display = 'block';
    alertDiv.classList.add('show');
}

/**
 * Hide error alert
 */
function hideErrorAlert() {
    const alertDiv = document.getElementById('error-alert');
    alertDiv.style.display = 'none';
    alertDiv.classList.remove('show');
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format timestamp to readable string
 * @param {Date} date - Date object
 * @returns {string} Formatted timestamp
 */
function formatTimestamp(date) {
    if (!(date instanceof Date) || isNaN(date)) {
        return '-';
    }
    
    const year = date.getUTCFullYear();
    const month = String(date.getUTCMonth() + 1).padStart(2, '0');
    const day = String(date.getUTCDate()).padStart(2, '0');
    const hours = String(date.getUTCHours()).padStart(2, '0');
    const minutes = String(date.getUTCMinutes()).padStart(2, '0');
    const seconds = String(date.getUTCSeconds()).padStart(2, '0');
    
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds} UTC`;
}

/**
 * Format number with fixed 3 decimal places
 * @param {number} num - Number to format
 * @returns {string} Formatted number
 */
function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) {
        return '-';
    }
    return Number(num).toFixed(3);
}

/**
 * Get datetime-local input value as ISO string
 * @param {string} elementId - Element ID of input
 * @returns {string|null} ISO datetime string or null
 */
function getDatetimeLocalAsISO(elementId) {
    const input = document.getElementById(elementId);
    if (!input || !input.value) return null;
    
    // datetime-local format: YYYY-MM-DDTHH:mm
    // Convert to ISO: YYYY-MM-DDTHH:mm:00Z
    return input.value + ':00Z';
}

/**
 * Convert ISO datetime to datetime-local format
 * @param {string} isoString - ISO datetime string
 * @returns {string} datetime-local format value
 */
function isoToDatetimeLocal(isoString) {
    if (!isoString) return '';
    // ISO format: 2024-01-15T10:30:00Z
    // datetime-local format: 2024-01-15T10:30
    return isoString.substring(0, 16);
}

// ============================================================================
// Event Handlers
// ============================================================================

/**
 * Handle "Fetch Stats" button click
 */
async function handleFetchStats() {
    const from = getDatetimeLocalAsISO('stats-from');
    const to = getDatetimeLocalAsISO('stats-to');

    if (!from || !to) {
        showErrorAlert('Please select both From and To dates for stats');
        return;
    }

    try {
        document.getElementById('stats-loading').style.display = 'block';
        document.getElementById('stats-content').style.display = 'none';

        const stats = await fetchStats({ from, to });
        updateStats(stats);
    } catch (error) {
        document.getElementById('stats-loading').style.display = 'none';
        showErrorAlert(`Failed to fetch stats: ${error.message}`);
    }
}

/**
 * Handle "Search History" button click
 */
async function handleSearchHistory() {
    const from = getDatetimeLocalAsISO('history-from');
    const to = getDatetimeLocalAsISO('history-to');
    const limit = parseInt(document.getElementById('history-limit').value) || 100;
    
    // Reset offset to 0 when doing new search
    DashboardState.currentOffset = 0;
    DashboardState.currentLimit = limit;
    DashboardState.currentFrom = from;
    DashboardState.currentTo = to;

    await loadHistory();
}

/**
 * Load history with current state parameters
 */
async function loadHistory() {
    try {
        document.getElementById('history-loading').style.display = 'block';
        document.getElementById('history-content').style.display = 'none';
        document.getElementById('no-data-message').style.display = 'none';

        const options = {
            limit: DashboardState.currentLimit,
            offset: DashboardState.currentOffset,
        };

        if (DashboardState.currentFrom) options.from = DashboardState.currentFrom;
        if (DashboardState.currentTo) options.to = DashboardState.currentTo;

        const result = await fetchHistory(options);
        
        DashboardState.totalRecords = result.total;
        updateHistoryTable(result.records);
        
        document.getElementById('history-loading').style.display = 'none';
    } catch (error) {
        document.getElementById('history-loading').style.display = 'none';
        showErrorAlert(`Failed to fetch history: ${error.message}`);
    }
}

/**
 * Handle "Previous" page button click
 */
async function handlePreviousPage() {
    const { currentOffset, currentLimit } = DashboardState;
    
    if (currentOffset >= currentLimit) {
        DashboardState.currentOffset = currentOffset - currentLimit;
        await loadHistory();
    }
}

/**
 * Handle "Next" page button click
 */
async function handleNextPage() {
    const { currentOffset, currentLimit, totalRecords } = DashboardState;
    
    if (currentOffset + currentLimit < totalRecords) {
        DashboardState.currentOffset = currentOffset + currentLimit;
        await loadHistory();
    }
}

// ============================================================================
// Auto-Refresh Latest
// ============================================================================

/**
 * Start auto-refresh of latest values (10 seconds)
 */
function startAutoRefresh() {
    // Initial fetch
    refreshLatest();
    
    // Set interval
    DashboardState.autoRefreshInterval = setInterval(refreshLatest, 10000);
}

/**
 * Stop auto-refresh
 */
function stopAutoRefresh() {
    if (DashboardState.autoRefreshInterval) {
        clearInterval(DashboardState.autoRefreshInterval);
        DashboardState.autoRefreshInterval = null;
    }
}

/**
 * Refresh latest values
 */
async function refreshLatest() {
    try {
        const data = await fetchLatest();
        updateLatestDisplay(data);
    } catch (error) {
        console.error('Error refreshing latest:', error);
        // Don't show alert for auto-refresh errors, just log
    }
}

// ============================================================================
// Initialize
// ============================================================================

/**
 * Initialize dashboard on page load
 */
async function initializeDashboard() {
    console.log('Initializing Network Speed Dashboard...');

    // Setup event listeners
    document.getElementById('fetch-stats-btn').addEventListener('click', handleFetchStats);
    document.getElementById('search-history-btn').addEventListener('click', handleSearchHistory);
    document.getElementById('prev-page-btn').addEventListener('click', handlePreviousPage);
    document.getElementById('next-page-btn').addEventListener('click', handleNextPage);

    // Set default date ranges (last 24 hours for stats)
    const now = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    
    document.getElementById('stats-from').value = isoToDatetimeLocal(yesterday.toISOString());
    document.getElementById('stats-to').value = isoToDatetimeLocal(now.toISOString());
    
    document.getElementById('history-from').value = isoToDatetimeLocal(yesterday.toISOString());
    document.getElementById('history-to').value = isoToDatetimeLocal(now.toISOString());

    // Start auto-refresh for latest values
    startAutoRefresh();

    // Load initial stats
    try {
        const from = getDatetimeLocalAsISO('stats-from');
        const to = getDatetimeLocalAsISO('stats-to');
        const stats = await fetchStats({ from, to });
        updateStats(stats);
    } catch (error) {
        console.error('Error loading initial stats:', error);
    }

    console.log('Dashboard initialization complete');
}

// ============================================================================
// Page Load
// ============================================================================

document.addEventListener('DOMContentLoaded', initializeDashboard);

// ============================================================================
// Aggregates & Charts
// ============================================================================

async function fetchAggregates({ from, to, groupBy, limit = 100, offset = 0 }) {
    try {
        const params = new URLSearchParams();
        if (from) params.append('from', from);
        if (to) params.append('to', to);
        if (groupBy) params.append('group_by', groupBy);
        params.append('limit', limit);
        params.append('offset', offset);

        const response = await fetch(`/api/dashboard/aggregates?${params.toString()}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        showError(`Failed to fetch aggregates: ${error.message}`);
        throw error;
    }
}

function updateAggregatesChart(data) {
    const container = document.getElementById('chart-container');
    const noDataMsg = document.getElementById('no-aggregates-message');
    const chartError = document.getElementById('chart-error');

    if (!data || !data.rows || data.rows.length === 0) {
        container.style.display = 'none';
        noDataMsg.style.display = 'block';
        chartError.style.display = 'none';
        return;
    }

    container.style.display = 'block';
    noDataMsg.style.display = 'none';
    chartError.style.display = 'none';

    const groupBy = data.group_by || 'none';
    let trace, layout;

    if (groupBy === 'weekday') {
        const weekdayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        const downloadAvgs = data.rows.map(r => r.download_avg || 0);
        const uploadAvgs = data.rows.map(r => r.upload_avg || 0);
        const groups = data.rows.map((r, i) => weekdayNames[parseInt(r.group)] || `Day ${r.group}`);

        const trace1 = { x: groups, y: downloadAvgs, name: 'Download (Mbps)', type: 'bar', marker: { color: 'rgba(54, 162, 235, 0.7)' } };
        const trace2 = { x: groups, y: uploadAvgs, name: 'Upload (Mbps)', type: 'bar', marker: { color: 'rgba(75, 192, 75, 0.7)' } };
        layout = {
            title: 'Weekday Pattern (Avg Speed by Day of Week)',
            xaxis: { title: 'Day of Week' },
            yaxis: { title: 'Speed (Mbps)' },
            barmode: 'group',
            hovermode: 'x'
        };
        Plotly.newPlot('chart-container', [trace1, trace2], layout, { responsive: true });
    } else if (groupBy === 'hour') {
        const downloadAvgs = data.rows.map(r => r.download_avg || 0);
        const uploadAvgs = data.rows.map(r => r.upload_avg || 0);
        const timestamps = data.rows.map(r => {
            const dt = new Date(r.group);
            return dt.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        });

        const downloadTrace = { x: timestamps, y: downloadAvgs, name: 'Download (Mbps)', type: 'scatter', mode: 'lines+markers', line: { color: 'rgb(54, 162, 235)', width: 2 } };
        const uploadTrace = { x: timestamps, y: uploadAvgs, name: 'Upload (Mbps)', type: 'scatter', mode: 'lines+markers', line: { color: 'rgb(75, 192, 75)', width: 2 } };
        layout = {
            title: 'Hourly Trend',
            xaxis: { title: 'Timestamp (UTC)' },
            yaxis: { title: 'Speed (Mbps)' },
            hovermode: 'x unified'
        };
        Plotly.newPlot('chart-container', [downloadTrace, uploadTrace], layout, { responsive: true });
    } else if (groupBy === 'day') {
        const downloadAvgs = data.rows.map(r => r.download_avg || 0);
        const uploadAvgs = data.rows.map(r => r.upload_avg || 0);
        const dates = data.rows.map(r => {
            const dt = new Date(r.group);
            return dt.toISOString().split('T')[0];
        });

        const downloadTrace = { x: dates, y: downloadAvgs, name: 'Download (Mbps)', type: 'scatter', mode: 'lines+markers', fill: 'tozeroy', line: { color: 'rgb(54, 162, 235)', width: 2 } };
        const uploadTrace = { x: dates, y: uploadAvgs, name: 'Upload (Mbps)', type: 'scatter', mode: 'lines+markers', fill: 'tozeroy', line: { color: 'rgb(75, 192, 75)', width: 2 } };
        layout = {
            title: 'Daily Trend',
            xaxis: { title: 'Date (UTC)' },
            yaxis: { title: 'Speed (Mbps)' },
            hovermode: 'x unified'
        };
        Plotly.newPlot('chart-container', [downloadTrace, uploadTrace], layout, { responsive: true });
    } else if (groupBy === 'season') {
        const downloadAvgs = data.rows.map(r => r.download_avg || 0);
        const uploadAvgs = data.rows.map(r => r.upload_avg || 0);
        const seasons = data.rows.map(r => r.group);

        const trace1 = { x: seasons, y: downloadAvgs, name: 'Download (Mbps)', type: 'bar', marker: { color: 'rgba(54, 162, 235, 0.7)' } };
        const trace2 = { x: seasons, y: uploadAvgs, name: 'Upload (Mbps)', type: 'bar', marker: { color: 'rgba(75, 192, 75, 0.7)' } };
        layout = {
            title: 'Seasonal Trend',
            xaxis: { title: 'Season' },
            yaxis: { title: 'Speed (Mbps)' },
            barmode: 'group'
        };
        Plotly.newPlot('chart-container', [trace1, trace2], layout, { responsive: true });
    } else {
        const timestamps = data.rows.map(r => {
            const dt = new Date(r.group);
            return dt.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        });
        const downloadAvgs = data.rows.map(r => r.download_avg || 0);
        const uploadAvgs = data.rows.map(r => r.upload_avg || 0);

        const downloadTrace = { x: timestamps, y: downloadAvgs, name: 'Download (Mbps)', type: 'scatter', mode: 'lines+markers', line: { color: 'rgb(54, 162, 235)', width: 2 } };
        const uploadTrace = { x: timestamps, y: uploadAvgs, name: 'Upload (Mbps)', type: 'scatter', mode: 'lines+markers', line: { color: 'rgb(75, 192, 75)', width: 2 } };
        layout = {
            title: 'Speed Over Time',
            xaxis: { title: 'Timestamp (UTC)' },
            yaxis: { title: 'Speed (Mbps)' },
            hovermode: 'x unified'
        };
        Plotly.newPlot('chart-container', [downloadTrace, uploadTrace], layout, { responsive: true });
    }
}

// Load aggregates chart event listener
document.addEventListener('DOMContentLoaded', () => {
    const loadBtn = document.getElementById('load-aggregates-btn');
    const typeSelect = document.getElementById('aggregate-type');
    
    if (loadBtn) {
        loadBtn.addEventListener('click', async () => {
            const groupBy = typeSelect.value;
            if (!groupBy) {
                alert('Please select a view type');
                return;
            }

            document.getElementById('aggregates-loading').style.display = 'block';
            document.getElementById('chart-container').style.display = 'none';
            document.getElementById('no-aggregates-message').style.display = 'none';
            document.getElementById('chart-error').style.display = 'none';

            try {
                const from = getDatetimeLocalAsISO('stats-from') || new Date(Date.now() - 30*24*60*60*1000).toISOString();
                const to = getDatetimeLocalAsISO('stats-to') || new Date().toISOString();
                const data = await fetchAggregates({ from, to, groupBy, limit: 500 });
                updateAggregatesChart(data);
            } catch (error) {
                console.error('Error loading aggregates:', error);
                document.getElementById('chart-error').textContent = `Error: ${error.message}`;
                document.getElementById('chart-error').style.display = 'block';
            } finally {
                document.getElementById('aggregates-loading').style.display = 'none';
            }
        });
    }
});
