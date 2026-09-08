let isRedirecting = false;

export function markRedirecting() {
  isRedirecting = true;
}

export function resetRedirectGuardOnAuth() {
  isRedirecting = false;
}

export function isAlreadyRedirecting() {
  return isRedirecting;
}
