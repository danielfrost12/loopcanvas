#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# LoopCanvas GPU Watchdog — NEVER LET THE GPU GO DOWN
#
# Keeps server.py + localtunnel alive 24/7. Checks every 15 seconds.
# Uses /api/health for real HTTP-level liveness (not just "process alive").
# Auto-restarts on any failure. Hard-restarts after 3 consecutive failures.
#
# Usage:
#   ./watchdog.sh              # Run in foreground
#   nohup ./watchdog.sh &      # Run persistently (survives terminal close)
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="/tmp/loopcanvas_watchdog.log"
SERVER_LOG="/tmp/loopcanvas_server.log"
TUNNEL_LOG="/tmp/localtunnel.log"
CHECK_INTERVAL=15
MAX_HEALTH_FAILURES=3
SERVER_PORT=8888
TUNNEL_SUBDOMAIN="loopcanvas-gpu"
HEALTH_URL="http://localhost:$SERVER_PORT/api/health"
TUNNEL_HEALTH_URL="https://$TUNNEL_SUBDOMAIN.loca.lt/api/health"

health_failures=0
tunnel_failures=0
cycle=0

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"
}

start_server() {
    log "[SERVER] Starting server.py on port $SERVER_PORT..."
    # Kill anything on the port
    lsof -ti:$SERVER_PORT 2>/dev/null | xargs kill -9 2>/dev/null || true
    sleep 2

    cd "$SCRIPT_DIR"
    LOOPCANVAS_SEED=1 LOOPCANVAS_MODE=fast python3 server.py >> "$SERVER_LOG" 2>&1 &
    local pid=$!
    log "[SERVER] Started with PID $pid"

    # Wait up to 20s for port to bind
    for i in {1..20}; do
        if lsof -ti:$SERVER_PORT >/dev/null 2>&1; then
            log "[SERVER] Port $SERVER_PORT bound after ${i}s"
            return 0
        fi
        sleep 1
    done
    log "[SERVER] WARNING: Port not bound after 20s"
    return 1
}

start_tunnel() {
    log "[TUNNEL] Starting localtunnel..."
    pkill -f "localtunnel.*--port $SERVER_PORT" 2>/dev/null || true
    pkill -f "lt --port $SERVER_PORT" 2>/dev/null || true
    sleep 2

    npx --yes localtunnel --port $SERVER_PORT --subdomain $TUNNEL_SUBDOMAIN >> "$TUNNEL_LOG" 2>&1 &
    local pid=$!
    log "[TUNNEL] Started with PID $pid — URL: https://$TUNNEL_SUBDOMAIN.loca.lt"
    sleep 4
    return 0
}

check_server_process() {
    lsof -ti:$SERVER_PORT >/dev/null 2>&1
}

check_server_health() {
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$HEALTH_URL" 2>/dev/null) || code="000"
    [ "$code" = "200" ]
}

check_tunnel_process() {
    pgrep -f "localtunnel.*--port $SERVER_PORT" >/dev/null 2>&1 || \
    pgrep -f "lt --port $SERVER_PORT" >/dev/null 2>&1
}

check_tunnel_health() {
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
        -H "Bypass-Tunnel-Reminder: true" \
        "$TUNNEL_HEALTH_URL" 2>/dev/null) || code="000"
    [ "$code" = "200" ]
}

log "═══════════════════════════════════════════════════════════"
log " LoopCanvas GPU Watchdog — BRUTE FORCE RELIABILITY"
log " Server port: $SERVER_PORT"
log " Tunnel: https://$TUNNEL_SUBDOMAIN.loca.lt"
log " Health check: every ${CHECK_INTERVAL}s"
log " Hard restart after: $MAX_HEALTH_FAILURES consecutive failures"
log "═══════════════════════════════════════════════════════════"

# ── Initial startup ──────────────────────────────────────────
if ! check_server_process; then
    start_server
fi

sleep 3

if ! check_tunnel_process; then
    start_tunnel
fi

# ── Main watchdog loop ───────────────────────────────────────
while true; do
    sleep $CHECK_INTERVAL
    cycle=$((cycle + 1))

    # ═══ CHECK 1: Server process alive? ═══
    if ! check_server_process; then
        log "[WATCHDOG] server.py PROCESS DEAD — immediate restart"
        start_server
        health_failures=0
        continue
    fi

    # ═══ CHECK 2: Server responds to HTTP health check? ═══
    if ! check_server_health; then
        health_failures=$((health_failures + 1))
        log "[WATCHDOG] Health check FAILED ($health_failures/$MAX_HEALTH_FAILURES)"

        if [ $health_failures -ge $MAX_HEALTH_FAILURES ]; then
            log "[WATCHDOG] *** HARD RESTART — $MAX_HEALTH_FAILURES consecutive failures ***"
            lsof -ti:$SERVER_PORT 2>/dev/null | xargs kill -9 2>/dev/null || true
            sleep 3
            start_server
            health_failures=0
        fi
    else
        if [ $health_failures -gt 0 ]; then
            log "[WATCHDOG] Server recovered after $health_failures failed checks"
        fi
        health_failures=0
    fi

    # ═══ CHECK 3: Tunnel process alive? ═══
    if ! check_tunnel_process; then
        log "[WATCHDOG] localtunnel PROCESS DEAD — immediate restart"
        start_tunnel
        tunnel_failures=0
        continue
    fi

    # ═══ CHECK 4: Tunnel actually forwarding? (every 3rd cycle) ═══
    if [ $((cycle % 3)) -eq 0 ]; then
        if ! check_tunnel_health; then
            tunnel_failures=$((tunnel_failures + 1))
            log "[WATCHDOG] Tunnel health FAILED ($tunnel_failures/$MAX_HEALTH_FAILURES)"

            if [ $tunnel_failures -ge $MAX_HEALTH_FAILURES ]; then
                log "[WATCHDOG] *** TUNNEL HARD RESTART ***"
                pkill -f "localtunnel.*--port $SERVER_PORT" 2>/dev/null || true
                pkill -f "lt --port $SERVER_PORT" 2>/dev/null || true
                sleep 3
                start_tunnel
                tunnel_failures=0
            fi
        else
            if [ $tunnel_failures -gt 0 ]; then
                log "[WATCHDOG] Tunnel recovered after $tunnel_failures failed checks"
            fi
            tunnel_failures=0
        fi
    fi

    # ═══ STATUS LOG: every 40 cycles (~10 min) ═══
    if [ $((cycle % 40)) -eq 0 ]; then
        local_ok="NO"
        tunnel_ok="NO"
        check_server_health && local_ok="YES"
        check_tunnel_health && tunnel_ok="YES"
        log "[STATUS] cycle=$cycle local_health=$local_ok tunnel_health=$tunnel_ok health_fails=$health_failures tunnel_fails=$tunnel_failures"
    fi
done
