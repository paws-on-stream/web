#!/usr/bin/env bash
# paws-bot-sim.sh — Telegram Bot simulator for Paws on Stream
# Simulates bot-to-API interactions for testing without a real Telegram bot.
#
# Usage: ./scripts/paws-bot-sim.sh <command> [args...]
#
# Commands:
#   send <message>              Simulate incoming message from participant
#   pending                     Show pending messages (moderation queue)
#   approve <message_id>        Approve a message
#   reject <message_id> [reason] Reject a message (reason: no_event|unknown|not_checkedin|banned|rate_limit|offline)
#   display <message_id>        Mark message as displayed
#   events                      List all events
#   create-event <name>         Create a new active event (2h window)
#   activate-event <event_id>   Activate an event
#   participants                List all participants
#   settings                    Show current settings
#   update-settings <key>=<val> Update a setting
#   devices                     List display devices
#   logs                        Show display logs
#   status                      Quick status overview
#
# Config:
#   Set these env vars or put them in .env file in the project root:
#     PAWS_API_URL     — Base URL (default: http://localhost:8000)
#     PAWS_API_TOKEN   — API auth token (default: reads from .env)

set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ── Config ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env if it exists
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

API_URL="${PAWS_API_URL:-http://localhost:8000}"
API_TOKEN="${PAWS_API_TOKEN:-${API_AUTH_TOKEN:-}}"

# ── Helper Functions ────────────────────────────────────────────────

usage() {
    echo -e "${CYAN}Paws on Stream — Bot Simulator 🐾${NC}"
    echo ""
    echo "Usage: $0 <command> [args...]"
    echo ""
    echo "Commands:"
    echo "  send <message>              Simulate incoming message"
    echo "  pending                     Show pending messages"
    echo "  approve <message_id>        Approve a message"
    echo "  reject <message_id> [reason] Reject a message"
    echo "  display <message_id>        Mark message as displayed"
    echo "  events                      List events"
    echo "  create-event <name>         Create new event (2h window)"
    echo "  activate-event <id>         Activate an event"
    echo "  participants                List participants"
    echo "  settings                    Show settings"
    echo "  update-settings <k>=<v>     Update a setting"
    echo "  devices                     List display devices"
    echo "  logs                        Show display logs"
    echo "  status                      Quick status overview"
    echo ""
    echo "Config (env vars or .env file):"
    echo "  PAWS_API_URL    Base URL (default: http://localhost:8000)"
    echo "  PAWS_API_TOKEN  API token (or API_AUTH_TOKEN from .env)"
    echo ""
    echo "Example:"
    echo "  $0 send 'Hey everyone!'"
    echo "  $0 pending"
    echo "  $0 approve abc123-def456"
}

# Make an API request and return JSON
api() {
    local method="$1"
    local endpoint="$2"
    shift 2
    local data=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --data) data="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    local headers=(-H "X-API-Token: $API_TOKEN" -H "Content-Type: application/json")

    if [[ -n "$data" ]]; then
        curl -s -X "$method" "${API_URL}${endpoint}" "${headers[@]}" -d "$data" | jq .
    else
        curl -s -X "$method" "${API_URL}${endpoint}" "${headers[@]}" | jq .
    fi
}

# Pretty print a JSON array of messages
pretty_messages() {
    local json="$1"
    local count
    count=$(echo "$json" | jq '.results | length // length' 2>/dev/null || echo "0")

    if [[ "$count" -eq 0 ]]; then
        echo -e "  ${YELLOW}No messages found.${NC}"
        return
    fi

    echo "$json" | jq -r '
        (.results // .)[] |
        "  \(.id | .[0:8])... | \(.participant.display_name): \(.content | .[0:60])\(.content | length > 60 | if . then "..." else "" end) [\(.status)]"
    '
}

# Pretty print events
pretty_events() {
    local json="$1"
    echo "$json" | jq -r '
        .[] |
        "  \(.id). \(.name) | \(.starts_at) → \(.ends_at) | \(.is_active | if . then "\($GREEN)ACTIVE\($NC)" else "inactive" end)"
    '
}

# ── Commands ────────────────────────────────────────────────────────

cmd_send() {
    local message="${1:-}"
    if [[ -z "$message" ]]; then
        echo -e "${RED}Usage: $0 send <message>${NC}"
        exit 1
    fi

    # Get first participant and first active event (or any event)
    local participant
    participant=$(api GET /api/v1/participants/ | jq -r '.results[0] // .[0] // empty' 2>/dev/null)

    if [[ -z "$participant" ]]; then
        echo -e "${YELLOW}No participants found. Creating test participant...${NC}"
        participant=$(api POST /api/v1/participants/ --data '{
            "telegram_id": 1000000001,
            "display_name": "TestBot Sim"
        }')
    fi

    local participant_id
    participant_id=$(echo "$participant" | jq -r '.id')

    # Get active event, or any event
    local event
    event=$(api GET /api/v1/events/ | jq -r '[.[] | select(.is_active == true)][0] // .[0] // empty' 2>/dev/null)

    if [[ -z "$event" ]]; then
        echo -e "${YELLOW}No events found. Creating test event...${NC}"
        local now
        now=$(date -u +"%Y-%m-%dT%H:%M:%S")
        local end
        end=$(date -u -d "+2 hours" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || date -u -v+2H +"%Y-%m-%dT%H:%M:%S")
        event=$(api POST /api/v1/events/ --data "{
            \"name\": \"Test Event\",
            \"starts_at\": \"$now\",
            \"ends_at\": \"$end\",
            \"is_active\": true
        }")
    fi

    local event_id
    event_id=$(echo "$event" | jq -r '.id')

    echo -e "${BLUE}Sending message as participant $participant_id → event $event_id:${NC}"
    echo -e "  ${CYAN}$message${NC}"

    local result
    result=$(api POST /api/v1/messages/ --data "{
        \"participant_id\": $participant_id,
        \"content\": \"$(echo "$message" | jq -R .s | tr -d '\n')\",
        \"event\": $event_id,
        \"status\": \"pending\"
    }")

    local msg_id
    msg_id=$(echo "$result" | jq -r '.id')
    echo -e "  ${GREEN}✅ Message sent (id: ${msg_id:0:8}...)${NC}"
}

cmd_pending() {
    echo -e "${CYAN}Pending Messages:${NC}"
    local result
    result=$(api GET /api/v1/messages/?status=pending)
    local count
    count=$(echo "$result" | jq '.results | length // length' 2>/dev/null || echo "0")

    if [[ "$count" -eq 0 ]]; then
        echo -e "  ${GREEN}Queue is empty! 🎉${NC}"
        return
    fi

    pretty_messages "$result"
    echo -e "\n  ${YELLOW}Total: $count pending${NC}"
}

cmd_approve() {
    local msg_id="${1:-}"
    if [[ -z "$msg_id" ]]; then
        echo -e "${RED}Usage: $0 approve <message_id>${NC}"
        exit 1
    fi

    local result
    result=$(api POST "/api/v1/messages/$msg_id/approve/")
    echo -e "  ${GREEN}✅ Message approved!${NC}"
}

cmd_reject() {
    local msg_id="${1:-}"
    local reason="${2:-unknown}"

    if [[ -z "$msg_id" ]]; then
        echo -e "${RED}Usage: $0 reject <message_id> [reason]${NC}"
        echo -e "  Reasons: no_event, unknown, not_checkedin, banned, rate_limit, offline"
        exit 1
    fi

    local result
    result=$(api POST "/api/v1/messages/$msg_id/reject/" --data "{\"rejection_reason\": \"$reason\"}")
    echo -e "  ${YELLOW}❌ Message rejected (reason: $reason)${NC}"
}

cmd_display() {
    local msg_id="${1:-}"
    if [[ -z "$msg_id" ]]; then
        echo -e "${RED}Usage: $0 display <message_id>${NC}"
        exit 1
    fi

    local result
    result=$(api POST "/api/v1/messages/$msg_id/display/")
    echo -e "  ${GREEN}📺 Message sent to display!${NC}"
}

cmd_events() {
    echo -e "${CYAN}Events:${NC}"
    local result
    result=$(api GET /api/v1/events/)
    pretty_events "$result"
}

cmd_create_event() {
    local name="${1:-}"
    if [[ -z "$name" ]]; then
        echo -e "${RED}Usage: $0 create-event <name>${NC}"
        exit 1
    fi

    local now
    now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local end
    # Try GNU date first, fall back to BSD date
    if date -u -d "+2 hours" +"%Y-%m-%dT%H:%M:%SZ" &>/dev/null; then
        end=$(date -u -d "+2 hours" +"%Y-%m-%dT%H:%M:%SZ")
    else
        end=$(date -u -v+2H +"%Y-%m-%dT%H:%M:%SZ")
    fi

    local result
    result=$(api POST /api/v1/events/ --data "{
        \"name\": \"$(echo "$name" | jq -R .s | tr -d '\n')\",
        \"starts_at\": \"$now\",
        \"ends_at\": \"$end\",
        \"is_active\": true,
        \"allow_messages\": true
    }")

    local event_id
    event_id=$(echo "$result" | jq -r '.id')
    echo -e "  ${GREEN}✅ Event created: $name (id: $event_id, active: true)${NC}"
    echo -e "  ${YELLOW}Window: $now → $end${NC}"
}

cmd_activate_event() {
    local event_id="${1:-}"
    if [[ -z "$event_id" ]]; then
        echo -e "${RED}Usage: $0 activate-event <event_id>${NC}"
        exit 1
    fi

    local result
    result=$(api PUT "/api/v1/events/$event_id/" --data '{"is_active": true}')
    echo -e "  ${GREEN}✅ Event $event_id activated!${NC}"
}

cmd_participants() {
    echo -e "${CYAN}Participants:${NC}"
    local result
    result=$(api GET /api/v1/participants/)
    local count
    count=$(echo "$result" | jq '.results | length // length' 2>/dev/null || echo "0")

    if [[ "$count" -eq 0 ]]; then
        echo -e "  ${YELLOW}No participants yet.${NC}"
        return
    fi

    echo "$result" | jq -r '
        (.results // .)[] |
        "  \(.id). \(.display_name) (TG:\(.telegram_id)) | \(.checked_in | if . then "\($GREEN)checked in\($NC)" else "not checked in" end) \(.banned | if . then "\($RED)🚫\($NC)" else "" end)"
    '
    echo -e "\n  ${YELLOW}Total: $count participants${NC}"
}

cmd_settings() {
    echo -e "${CYAN}Settings:${NC}"
    local result
    result=$(api GET /api/v1/settings/)
    echo "$result" | jq -r '
        "  rate_limit_per_minute: \(.rate_limit_per_minute)
         max_message_length: \(.max_message_length)
         bot_status: \(.bot_status)
         auto_approve: \(.auto_approve)
         display_duration_sec: \(.display_duration_sec)
         display_mode: \(.display_mode)
         scroll_speed_px: \(.scroll_speed_px)
         overlay_theme: \(.overlay_theme)
         overlay_font_size: \(.overlay_font_size)
         require_event_active: \(.require_event_active)"
    '
}

cmd_update_settings() {
    local kv="${1:-}"
    if [[ -z "$kv" ]]; then
        echo -e "${RED}Usage: $0 update-settings <key>=<value>${NC}"
        echo -e "  Examples:"
        echo -e "    $0 update-settings auto_approve=true"
        echo -e "    $0 update-settings bot_status=online"
        echo -e "    $0 update-settings rate_limit_per_minute=30"
        exit 1
    fi

    local key="${kv%%=*}"
    local value="${kv#*=}"

    # Get current settings, update the key, PUT back
    local current
    current=$(api GET /api/v1/settings/)
    local updated
    updated=$(echo "$current" | jq --arg k "$key" --arg v "$value" '
        if ($v | test("^[0-9]+$")) then .[$k] = ($v | tonumber)
        elif ($v == "true" or $v == "false") then .[$k] = ($v | tonumber)
        else .[$k] = $v
        end
    ')

    api PUT /api/v1/settings/ --data "$updated" > /dev/null
    echo -e "  ${GREEN}✅ Setting updated: $key = $value${NC}"
}

cmd_devices() {
    echo -e "${CYAN}Display Devices:${NC}"
    local result
    result=$(api GET /api/v1/devices/)
    local count
    count=$(echo "$result" | jq '.results | length // length' 2>/dev/null || echo "0")

    if [[ "$count" -eq 0 ]]; then
        echo -e "  ${YELLOW}No devices registered.${NC}"
        return
    fi

    echo "$result" | jq -r '
        (.results // .)[] |
        "  \(.device_id) | \(.hostname) | \(.location | if . then . else "unknown" end) | \(.is_active | if . then "\($GREEN)active\($NC)" else "offline" end)"
    '
    echo -e "\n  ${YELLOW}Total: $count devices${NC}"
}

cmd_logs() {
    echo -e "${CYAN}Display Logs (last 20):${NC}"
    local result
    result=$(api GET /api/v1/logs/?limit=20)
    local count
    count=$(echo "$result" | jq '.results | length // length' 2>/dev/null || echo "0")

    if [[ "$count" -eq 0 ]]; then
        echo -e "  ${YELLOW}No display logs yet.${NC}"
        return
    fi

    echo "$result" | jq -r '
        (.results // .)[] |
        "  \(.displayed_at) | \(.message.participant.display_name) on \(.device.hostname)"
    '
}

cmd_status() {
    echo -e "${CYAN}🐾 Paws on Stream — Status${NC}"
    echo ""

    # Check if API is reachable
    if ! curl -s "${API_URL}/api/v1/events/" > /dev/null 2>&1; then
        echo -e "  ${RED}⚠️ API not reachable at $API_URL${NC}"
        echo -e "  Make sure Django dev server is running: python manage.py runserver"
        return 1
    fi
    echo -e "  ${GREEN}✅ API reachable at $API_URL${NC}"

    # Events
    local events
    events=$(api GET /api/v1/events/ 2>/dev/null || echo "[]")
    local active_events
    active_events=$(echo "$events" | jq '[.[] | select(.is_active == true)] | length')
    echo -e "  Events: $(echo "$events" | jq 'length') total, ${GREEN}$active_events active${NC}"

    # Participants
    local participants
    participants=$(api GET /api/v1/participants/ 2>/dev/null || echo '{"results":[]}')
    local participant_count
    participant_count=$(echo "$participants" | jq '.results | length // length')
    local checked_in
    checked_in=$(echo "$participants" | jq '[.results[]? // .[]? | select(.checked_in == true)] | length')
    echo -e "  Participants: $participant_count total, $checked_in checked in"

    # Pending messages
    local pending
    pending=$(api GET /api/v1/messages/?status=pending 2>/dev/null || echo '{"results":[]}')
    local pending_count
    pending_count=$(echo "$pending" | jq '.results | length // length')
    local status_color
    if [[ "$pending_count" -eq 0 ]]; then
        status_color="$GREEN"
    else
        status_color="$YELLOW"
    fi
    echo -e "  Pending messages: ${status_color}$pending_count${NC}"

    # Settings
    local settings
    settings=$(api GET /api/v1/settings/ 2>/dev/null || echo '{}')
    local bot_status
    bot_status=$(echo "$settings" | jq -r '.bot_status // "unknown"')
    local auto_approve
    auto_approve=$(echo "$settings" | jq -r '.auto_approve // false')
    echo -e "  Bot: ${GREEN}$bot_status${NC} | Auto-approve: $auto_approve"

    # Devices
    local devices
    devices=$(api GET /api/v1/devices/ 2>/dev/null || echo '{"results":[]}')
    local device_count
    device_count=$(echo "$devices" | jq '.results | length // length')
    local active_devices
    active_devices=$(echo "$devices" | jq '[.results[]? // .[]? | select(.is_active == true)] | length')
    echo -e "  Devices: $device_count total, $active_devices active"
}

# ── Main ────────────────────────────────────────────────────────────

if [[ $# -eq 0 ]]; then
    usage
    exit 0
fi

command="$1"
shift

# Check API token
if [[ -z "$API_TOKEN" && "$command" != "status" ]]; then
    echo -e "${YELLOW}⚠️  No API token set. Set PAWS_API_TOKEN or API_AUTH_TOKEN in .env${NC}"
    echo -e "    (Requests will work if middleware is disabled or token is set)${NC}"
fi

case "$command" in
    send)           cmd_send "$@" ;;
    pending)        cmd_pending ;;
    approve)        cmd_approve "$@" ;;
    reject)         cmd_reject "$@" ;;
    display)        cmd_display "$@" ;;
    events)         cmd_events ;;
    create-event)   cmd_create_event "$@" ;;
    activate-event) cmd_activate_event "$@" ;;
    participants)   cmd_participants ;;
    settings)       cmd_settings ;;
    update-settings) cmd_update_settings "$@" ;;
    devices)        cmd_devices ;;
    logs)           cmd_logs ;;
    status)         cmd_status ;;
    help|--help|-h) usage ;;
    *)
        echo -e "${RED}Unknown command: $command${NC}"
        usage
        exit 1
        ;;
esac
