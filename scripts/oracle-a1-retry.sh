#!/usr/bin/env bash
# Keep trying to launch an Always Free Ampere A1 instance until capacity frees up,
# and email you (via OCI Notifications) when it succeeds or stops on an error.
#
# Runs on any machine with a configured OCI CLI (e.g. the E2.1.Micro hub).
#
# One-time setup:
#   python3 -m venv ~/oci-venv && ~/oci-venv/bin/pip install oci-cli
#   ~/oci-venv/bin/oci setup config      # passphrase: N/A
#   upload ~/.oci/oci_api_key_public.pem: Profile -> My profile -> API keys -> Add API key
#
# Put your values in ~/.a1-retry.env (so the script itself never needs editing):
#   SUBNET_ID=ocid1.subnet.oc1.ap-hyderabad-1....     # the PUBLIC subnet, not the VCN
#   AD=XXXX:AP-HYDERABAD-1-AD-1                        # oci iam availability-domain list
#   NOTIFY_TOPIC_ID=ocid1.onstopic.oc1....             # optional, for email alerts
#
# Run in the background:
#   tmux new -s a1 'bash ~/oracle-a1-retry.sh; read -p "Script stopped. Press Enter to close."'
#   detach with Ctrl+B then D (not Ctrl+Z, which pauses the script)
set -uo pipefail

ENV_FILE="${ENV_FILE:-$HOME/.a1-retry.env}"
# shellcheck source=/dev/null
[[ -f "$ENV_FILE" ]] && source "$ENV_FILE"

OCI="${OCI:-$HOME/oci-venv/bin/oci}"
# Default compartment = tenancy root, read from the CLI config.
COMPARTMENT_ID="${COMPARTMENT_ID:-$(grep -m1 '^tenancy=' "$HOME/.oci/config" 2>/dev/null | cut -d= -f2)}"
SUBNET_ID="${SUBNET_ID:-CHANGE_ME}"
AD="${AD:-CHANGE_ME}"
NOTIFY_TOPIC_ID="${NOTIFY_TOPIC_ID:-}"
SSH_PUBKEY_FILE="${SSH_PUBKEY_FILE:-$HOME/.ssh/authorized_keys}"  # key you'll log in with
NAME="${NAME:-a1-dev-01}"
OCPUS="${OCPUS:-1}"            # start small; resize to 4 / 24 GB later
MEMORY_GB="${MEMORY_GB:-6}"
BOOT_GB="${BOOT_GB:-50}"       # keep ALL boot + block volumes <= 200 GB total
SLEEP_SECONDS="${SLEEP_SECONDS:-900}"   # 15 min between attempts; don't hammer the API
JITTER="${JITTER:-60}"                 # extra random 0..JITTER-1 seconds

log() { printf '%s  %s\n' "$(date '+%F %T')" "$*"; }

# Email via OCI Notifications (Always Free tier includes 1,000 emails/month).
notify() {
  [[ -n "$NOTIFY_TOPIC_ID" ]] || return 0
  if "$OCI" ons message publish --topic-id "$NOTIFY_TOPIC_ID" \
      --title "$1" --body "$2" >/dev/null 2>&1; then
    log "Email sent: $1"
  else
    log "Could not send email (check NOTIFY_TOPIC_ID)"
  fi
}

[[ -n "$COMPARTMENT_ID" ]] || { echo "No tenancy in ~/.oci/config; set COMPARTMENT_ID." >&2; exit 1; }
for v in SUBNET_ID AD; do
  if [[ "${!v}" == *CHANGE_ME* ]]; then echo "Set $v in $ENV_FILE first." >&2; exit 1; fi
done
[[ "$SUBNET_ID" == ocid1.subnet.* ]] || { echo "SUBNET_ID must be a subnet OCID (ocid1.subnet...), not a VCN." >&2; exit 1; }
[[ -s "$SSH_PUBKEY_FILE" ]] || { echo "SSH public key file not found: $SSH_PUBKEY_FILE" >&2; exit 1; }

IMAGE_ID="${IMAGE_ID:-$("$OCI" compute image list \
  --compartment-id "$COMPARTMENT_ID" \
  --operating-system "Canonical Ubuntu" --operating-system-version "24.04" \
  --shape "VM.Standard.A1.Flex" --sort-by TIMECREATED --sort-order DESC \
  --query 'data[0].id' --raw-output)}"
[[ "$IMAGE_ID" == ocid1.image.* ]] || { echo "Could not find an Ubuntu 24.04 A1 image: $IMAGE_ID" >&2; exit 1; }
log "Image: $IMAGE_ID"
alerts=off; [[ -n "$NOTIFY_TOPIC_ID" ]] && alerts=on
log "Trying $OCPUS OCPU / $MEMORY_GB GB every $SLEEP_SECONDS s. Email alerts: $alerts"

attempt=0
while true; do
  attempt=$((attempt + 1))
  out=$("$OCI" compute instance launch \
    --compartment-id "$COMPARTMENT_ID" \
    --availability-domain "$AD" \
    --display-name "$NAME" \
    --shape "VM.Standard.A1.Flex" \
    --shape-config "{\"ocpus\": $OCPUS, \"memoryInGBs\": $MEMORY_GB}" \
    --image-id "$IMAGE_ID" \
    --subnet-id "$SUBNET_ID" \
    --assign-public-ip true \
    --boot-volume-size-in-gbs "$BOOT_GB" \
    --ssh-authorized-keys-file "$SSH_PUBKEY_FILE" 2>&1)
  rc=$?

  if [[ $rc -eq 0 ]]; then
    log "SUCCESS on attempt $attempt. Instance is being created:"
    echo "$out" | grep -E '"(id|display-name|lifecycle-state)"' | head -5
    log "Find its public IP in Compute -> Instances in a minute or two."
    notify "Oracle A1 created: $NAME" \
      "Got a VM.Standard.A1.Flex ($OCPUS OCPU / $MEMORY_GB GB) on attempt $attempt at $(date '+%F %T %Z'). Check Compute -> Instances for the public IP."
    exit 0
  fi

  if grep -qiE 'out of (host )?capacity' <<<"$out"; then
    log "Attempt $attempt: out of capacity. Next try in $((SLEEP_SECONDS / 60)) min."
  elif grep -qiE 'TooManyRequests|429' <<<"$out"; then
    log "Attempt $attempt: rate limited. Backing off 30 min."
    sleep 1800
    continue
  else
    log "Attempt $attempt failed with a different error, stopping so you can check it:"
    echo "$out"
    notify "Oracle A1 retry stopped" \
      "Attempt $attempt failed with an unexpected error at $(date '+%F %T %Z'). SSH in and run: tmux attach -t a1"
    exit 1
  fi
  # small random jitter so retries don't land on the same second every time
  sleep $((SLEEP_SECONDS + RANDOM % JITTER))
done
