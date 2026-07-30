/**
 * URL Sanitizer & Security Utilities
 * Prevents DOM-based XSS attacks via javascript:, data:, or vbscript: protocol execution
 * and enforces safe http/https protocol navigation.
 */
export function sanitizeUrl(url) {
  if (!url || typeof url !== 'string') return '#';
  const trimmed = url.trim();

  // Block executable or inline data script protocols
  const lower = trimmed.toLowerCase();
  if (
    lower.startsWith('javascript:') ||
    lower.startsWith('data:') ||
    lower.startsWith('vbscript:') ||
    lower.startsWith('file:')
  ) {
    return '#';
  }

  // Prepend https:// if valid domain without scheme
  if (!lower.startsWith('http://') && !lower.startsWith('https://')) {
    if (/^[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/.test(trimmed)) {
      return `https://${trimmed}`;
    }
  }

  return trimmed;
}
