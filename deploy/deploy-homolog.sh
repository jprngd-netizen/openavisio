#!/bin/sh
# Deploy a tagged release to a homolog (staging) environment.
#
# Same push model as deploy.sh but with homolog-specific safeguards:
#   - Validates MEMED_ENVIRONMENT=integration (rejects production credentials)
#   - Dry-run mode for local testing without SSH
#   - Idempotent: git archive contains only TRACKED files, no --delete anywhere
#
# Usage:
#   ./deploy/deploy-homolog.sh <ssh-target> <tag> [remote-dir]              # real deploy
#   ./deploy/deploy-homolog.sh --dry-run <ssh-target> <tag> [remote-dir]    # simulate
#   ./deploy/deploy-homolog.sh --dry-run --local <tag>                      # local dry-run
#
# Examples:
#   ./deploy/deploy-homolog.sh root@homolog-box v0.2.0
#   ./deploy/deploy-homolog.sh --dry-run root@homolog-box v0.2.0
#   ./deploy/deploy-homolog.sh --dry-run --local v0.2.0
#
# Exit codes:
#   0 — success
#   1 — validation or deploy failure
#   2 — usage error
set -eu

# ── config ────────────────────────────────────────────────────────────────────
HOMOLOG_ENV_FILE=".env.homolog"          # expected env file on the remote
REQUIRED_HOMOLOG_ENV="integration"       # MEMED_ENVIRONMENT must be this
BACKEND_HEALTH_TIMEOUT=40                # iterations (×5s = 200s)

# ── colours (only in dry-run) ──────────────────────────────────────────────────
if [ -t 1 ] && command -v tput &>/dev/null; then
  BOLD=$(tput bold); RESET=$(tput sgr0)
  GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3); RED=$(tput setaf 1); CYAN=$(tput setaf 6)
else
  BOLD=''; RESET=''; GREEN=''; YELLOW=''; RED=''; CYAN=''
fi

ok()   { echo "${GREEN}  ✓${RESET} $*"; }
warn() { echo "${YELLOW}  ⚠${RESET} $*"; }
fail() { echo "${RED}  ✗${RESET} $*" >&2; }
info() { echo "${CYAN}  ➜${RESET} $*"; }
header() { echo; echo "${BOLD}━━━  $*  ━━━${RESET}"; echo; }

# ── parse flags ────────────────────────────────────────────────────────────────
DRY_RUN=false
LOCAL=false
POSITIONAL=""

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --local)   LOCAL=true ;;
    -h|--help)
      echo "Usage: $0 [--dry-run] [--local] <ssh-target> <tag> [remote-dir]"
      echo "  --dry-run    simulate the deploy (no SSH, no docker compose)"
      echo "  --local      dry-run against the local filesystem instead of SSH"
      echo "  --help       this message"
      exit 0 ;;
    -*)
      echo "unknown flag: $arg" >&2; exit 2 ;;
    *)
      POSITIONAL="$POSITIONAL $arg" ;;
  esac
done

# shellcheck disable=SC2086
set -- $POSITIONAL

if [ "$LOCAL" = true ] && [ "$DRY_RUN" = false ]; then
  fail "--local requires --dry-run"
  exit 2
fi

if [ "$LOCAL" = false ]; then
  [ $# -ge 2 ] || { echo "usage: $0 [--dry-run] <ssh-target> <tag> [remote-dir]" >&2; exit 2; }
  TARGET=$1
  TAG=$2
  DIR=${3:-/opt/openavisio}
else
  [ $# -ge 1 ] || { echo "usage: $0 --dry-run --local <tag> [local-dir]" >&2; exit 2; }
  TAG=$1
  DIR=${2:-/tmp/openavisio-homolog-dryrun}
  TARGET="local"
fi

# ── phase 1: tag validation ────────────────────────────────────────────────────
header "Phase 1: Tag validation"

# Must be an annotated tag (not a branch, not a lightweight tag)
if git rev-parse -q --verify "refs/tags/$TAG^{tag}" >/dev/null 2>&1; then
  ok "Tag '$TAG' is an annotated tag"
else
  fail "'$TAG' is not an annotated tag — see docs/releasing.md"
  exit 1
fi

# Must be pushed to origin (so the remote can pull if needed, and we know it's published)
if git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null 2>&1; then
  ok "Tag '$TAG' is on origin"
else
  fail "Tag '$TAG' is not on origin — push it first: git push origin $TAG"
  exit 1
fi

# ── phase 2: env validation (dry-run safe) ─────────────────────────────────────
header "Phase 2: Environment validation"

if [ "$DRY_RUN" = true ]; then
  info "DRY RUN — checking local .env for homolog compliance"
  ENV_CHECK_FILE=".env"
else
  info "Checking remote $TARGET:$DIR for homolog compliance"
  # Fetch the remote .env (or .env.homolog) for validation
  ENV_CONTENT=$(ssh "$TARGET" "cat '$DIR/$HOMOLOG_ENV_FILE' 2>/dev/null || cat '$DIR/.env' 2>/dev/null || true")
  ENV_CHECK_FILE="$HOMOLOG_ENV_FILE"
fi

# Validate MEMED_ENVIRONMENT
if [ "$DRY_RUN" = true ]; then
  MEMED_ENV=$(grep -m1 '^MEMED_ENVIRONMENT=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || echo "")
else
  MEMED_ENV=$(echo "$ENV_CONTENT" | grep -m1 '^MEMED_ENVIRONMENT=' | cut -d= -f2- | tr -d '"' || echo "")
fi

if [ "$MEMED_ENV" = "$REQUIRED_HOMOLOG_ENV" ]; then
  ok "MEMED_ENVIRONMENT=$MEMED_ENV (expected $REQUIRED_HOMOLOG_ENV)"
else
  fail "MEMED_ENVIRONMENT is '$MEMED_ENV' but homolog requires '$REQUIRED_HOMOLOG_ENV'"
  fail "Set MEMED_ENVIRONMENT=$REQUIRED_HOMOLOG_ENV in $ENV_CHECK_FILE on the target"
  exit 1
fi

# Validate MEMED_API_URL points to homolog (not production)
if [ "$DRY_RUN" = true ]; then
  MEMED_API=$(grep -m1 '^MEMED_API_URL=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || echo "")
else
  MEMED_API=$(echo "$ENV_CONTENT" | grep -m1 '^MEMED_API_URL=' | cut -d= -f2- | tr -d '"' || echo "")
fi

case "$MEMED_API" in
  *integrations*|*homolog*|*staging*|*test*|"")
    ok "MEMED_API_URL points to homolog ($MEMED_API)"
    ;;
  *)
    fail "MEMED_API_URL='$MEMED_API' looks like PRODUCTION — homolog must use integrations API"
    fail "Set MEMED_API_URL=https://integrations.api.memed.com.br/v1 in $ENV_CHECK_FILE"
    exit 1
    ;;
esac

# Validate MEMED_SCRIPT_URL points to homolog
if [ "$DRY_RUN" = true ]; then
  MEMED_SCRIPT=$(grep -m1 '^MEMED_SCRIPT_URL=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || echo "")
else
  MEMED_SCRIPT=$(echo "$ENV_CONTENT" | grep -m1 '^MEMED_SCRIPT_URL=' | cut -d= -f2- | tr -d '"' || echo "")
fi

case "$MEMED_SCRIPT" in
  *integrations*|*homolog*|*staging*|*test*|"")
    ok "MEMED_SCRIPT_URL points to homolog ($MEMED_SCRIPT)"
    ;;
  *)
    fail "MEMED_SCRIPT_URL='$MEMED_SCRIPT' looks like PRODUCTION"
    fail "Set MEMED_SCRIPT_URL to the homolog script URL in $ENV_CHECK_FILE"
    exit 1
    ;;
esac

# Warn if AGE_PUBKEY is empty (backups won't work, but deploy can proceed)
if [ "$DRY_RUN" = true ]; then
  AGE_KEY=$(grep -m1 '^AGE_PUBKEY=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || echo "")
else
  AGE_KEY=$(echo "$ENV_CONTENT" | grep -m1 '^AGE_PUBKEY=' | cut -d= -f2- | tr -d '"' || echo "")
fi

if [ -z "$AGE_KEY" ]; then
  warn "AGE_PUBKEY is empty — backups will fail. Set it before going live."
else
  ok "AGE_PUBKEY is set"
fi

# ── phase 3: archive & transfer (dry-run skips SSH) ────────────────────────────
header "Phase 3: Archive and transfer"

if [ "$DRY_RUN" = true ]; then
  info "DRY RUN — would stream tag '$TAG' to $TARGET:$DIR"
  info "Archive contents (first 20 entries):"
  git archive --format=tar "$TAG" | tar -t 2>/dev/null | head -20
  echo "  ... ($(git archive --format=tar "$TAG" | wc -c) bytes total)"
  echo ""

  if [ "$LOCAL" = true ]; then
    info "LOCAL DRY RUN — extracting to $DIR for inspection"
    mkdir -p "$DIR"
    git archive --format=tar "$TAG" | tar -x --no-same-owner -C "$DIR"
    ok "Extracted to $DIR"
    info "  ls $DIR:"
    ls -la "$DIR" | head -10
    echo "  ..."
  fi
else
  info "Streaming tag '$TAG' to $TARGET:$DIR"
  git archive --format=tar "$TAG" | ssh "$TARGET" "tar -x --no-same-owner -C '$DIR'"
  ok "Transfer complete"
fi

# ── phase 4: rebuild & health check (dry-run skips) ────────────────────────────
header "Phase 4: Rebuild and health check"

if [ "$DRY_RUN" = true ]; then
  info "DRY RUN — would run on $TARGET:"
  echo "    cd $DIR"
  echo "    docker compose up -d --build"
  echo "    wait for backend health (up to ${BACKEND_HEALTH_TIMEOUT}×5s = $((BACKEND_HEALTH_TIMEOUT * 5))s)"
  echo "    docker compose ps"
  echo ""
  info "DRY RUN complete — no changes made to any running system."
else
  ssh "$TARGET" "sh -s -- '$DIR'" <<'REMOTE'
set -eu
cd "$1"

# Homolog env file: if .env.homolog exists, symlink it as .env so compose picks it up
if [ -f ".env.homolog" ] && [ ! -f ".env" ]; then
  ln -sf ".env.homolog" ".env"
  echo "==> linked .env.homolog -> .env"
fi

docker compose up -d --build
cid=$(docker compose ps -q backend 2>/dev/null || true)
if [ -z "$cid" ]; then
  echo "FAIL: no backend container found" >&2
  docker compose ps >&2
  exit 1
fi

echo "==> waiting for backend health"
i=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null)" = "healthy" ]; do
  i=$((i + 1))
  if [ "$i" -ge 40 ]; then
    echo "FAIL: backend not healthy after ~200s — rolling nothing back, box left as-is" >&2
    docker compose logs --tail=40 backend >&2
    exit 1
  fi
  sleep 5
done
docker compose ps
REMOTE

  ok "Backend healthy — deploy complete"
fi

# ── summary ────────────────────────────────────────────────────────────────────
header "Summary"
if [ "$DRY_RUN" = true ]; then
  echo "  Mode:       DRY RUN${LOCAL:+ (local)}"
  echo "  Tag:        $TAG"
  echo "  Target:     $TARGET:$DIR"
  echo "  Status:     SIMULATED (no changes made)"
  echo ""
  echo "  To deploy for real, run:"
  echo "    $0 $TARGET $TAG $DIR"
else
  echo "  Mode:       DEPLOY"
  echo "  Tag:        $TAG"
  echo "  Target:     $TARGET:$DIR"
  echo "  Status:     OK"
fi
echo ""