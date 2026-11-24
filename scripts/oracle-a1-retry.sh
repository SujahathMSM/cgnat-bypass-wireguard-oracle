#!/usr/bin/env bash
# Keep trying to launch an Always Free Ampere A1 instance until capacity frees up.
#
# Runs on any machine with a configured OCI CLI (e.g. the E2.1.Micro hub).
# Stops on success, or on any error that is NOT "out of capacity".
#
# One-time setup:
#   python3 -m venv ~/oci-venv && ~/oci-venv/bin/pip install oci-cli
#   ~/oci-venv/bin/oci setup config      # then upload the printed public key:
#                                         # Profile -> My profile -> API keys -> Add API key
#
# Fill in the variables below (see "Finding the values"), then:
#   tmux new -s a1 './oracle-a1-retry.sh'       # detach with Ctrl+b then d
#
# Finding the values:
#   COMPARTMENT_ID  tenancy OCID: Profile -> Tenancy -> OCID
#   SUBNET_ID       Networking -> VCN dev-01 -> public subnet-dev-01 -> OCID
#   AD              oci iam availability-domain list --query 'data[0].name' --raw-output
#   IMAGE_ID        found automatically below (latest Ubuntu 24.04 for A1)
set -uo pipefail

OCI="${OCI:-$HOME/oci-venv/bin/oci}"
COMPARTMENT_ID="${COMPARTMENT_ID:-ocid1.tenancy.oc1..CHANGE_ME}"
SUBNET_ID="${SUBNET_ID:-ocid1.subnet.oc1.ap-hyderabad-1.CHANGE_ME}"
AD="${AD:-CHANGE_ME:AP-HYDERABAD-1-AD-1}"
SSH_PUBKEY_FILE="${SSH_PUBKEY_FILE:-$HOME/.ssh/authorized_keys}"  # key you'll log in with
NAME="${NAME:-a1-dev-01}"
OCPUS="${OCPUS:-1}"            # start small; resize to 4 / 24 GB later
MEMORY_GB="${MEMORY_GB:-6}"
BOOT_GB="${BOOT_GB:-50}"       # keep ALL boot + block volumes <= 200 GB total
SLEEP_SECONDS="${SLEEP_SECONDS:-900}"   # 15 min between attempts; don't hammer the API

log() { printf '%s  %s\n' "$(date '+%F %T')" "$*"; }

for v in COMPARTMENT_ID SUBNET_ID AD; do
  if [[ "${!v}" == *CHANGE_ME* ]]; then echo "Set $v first." >&2; exit 1; fi
done
[[ -s "$SSH_PUBKEY_FILE" ]] || { echo "SSH public key file not found: $SSH_PUBKEY_FILE" >&2; exit 1; }

IMAGE_ID="${IMAGE_ID:-$("$OCI" compute image list \
  --compartment-id "$COMPARTMENT_ID" \
  --operating-system "Canonical Ubuntu" --operating-system-version "24.04" \
  --shape "VM.Standard.A1.Flex" --sort-by TIMECREATED --sort-order DESC \
  --query 'data[0].id' --raw-output)}"
[[ "$IMAGE_ID" == ocid1.image.* ]] || { echo "Could not find an Ubuntu 24.04 A1 image: $IMAGE_ID" >&2; exit 1; }
log "Image: $IMAGE_ID"
log "Trying $OCPUS OCPU / $MEMORY_GB GB every $SLEEP_SECONDS s. Ctrl+C to stop."

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
    exit 1
  fi
  # small random jitter so retries don't land on the same second every time
  sleep $((SLEEP_SECONDS + RANDOM % 60))
done
