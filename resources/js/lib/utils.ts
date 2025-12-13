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

/**
 * Formats a date string as relative time (e.g., "2 hours ago", "3 days ago").
 *
 * @param dateString - The date string to format
 * @returns A human-readable relative time string
 */
export function formatRelativeTime(
  dateString: string | null | undefined,
): string {
  if (!dateString) {
    return 'N/A';
  }

  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) {
    return 'just now';
  }

  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) {
    return `${diffInMinutes} minute${diffInMinutes !== 1 ? 's' : ''} ago`;
  }

  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) {
    return `${diffInHours} hour${diffInHours !== 1 ? 's' : ''} ago`;
  }

  const diffInDays = Math.floor(diffInHours / 24);
  if (diffInDays < 30) {
    return `${diffInDays} day${diffInDays !== 1 ? 's' : ''} ago`;
  }

  const diffInMonths = Math.floor(diffInDays / 30);
  if (diffInMonths < 12) {
    return `${diffInMonths} month${diffInMonths !== 1 ? 's' : ''} ago`;
  }

  const diffInYears = Math.floor(diffInMonths / 12);
  return `${diffInYears} year${diffInYears !== 1 ? 's' : ''} ago`;
}
