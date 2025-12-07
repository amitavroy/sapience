import { InertiaLinkProps } from '@inertiajs/react';
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function isSameUrl(
  url1: NonNullable<InertiaLinkProps['href']>,
  url2: NonNullable<InertiaLinkProps['href']>,
) {
  return resolveUrl(url1) === resolveUrl(url2);
}

export function resolveUrl(url: NonNullable<InertiaLinkProps['href']>): string {
  return typeof url === 'string' ? url : url.url;
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) {
    return '0 Bytes';
  }
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Converts a Laravel pagination URL (which may be a full URL) to a relative URL
 * suitable for use with fetch() or other client-side requests.
 *
 * @param url - The URL from Laravel pagination (can be full URL or relative URL)
 * @returns A relative URL (pathname + search params)
 */
export function toRelativeUrl(url: string | null | undefined): string {
  if (!url) {
    return '';
  }

  try {
    // If it's already a relative URL, return as-is
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      return url;
    }

    // Convert full URL to relative URL
    const urlObj = new URL(url);
    return urlObj.pathname + urlObj.search;
  } catch {
    // If URL parsing fails, return the original string
    return url;
  }
}
