import { InertiaLinkProps } from '@inertiajs/react';
import { LucideIcon } from 'lucide-react';

export interface Auth {
  user: User;
}

export interface BreadcrumbItem {
  title: string;
  href: string;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export interface NavItem {
  title: string;
  href: NonNullable<InertiaLinkProps['href']>;
  icon?: LucideIcon | null;
  isActive?: boolean;
}

export interface Organisation {
  id: number;
  uuid: string;
  name: string;
}

export interface Owner {
  id: number;
  name: string;
}

export interface Dataset {
  id: number;
  uuid: string;
  name: string;
  description: string | null;
  is_active: boolean;
  files_count: number;
  owner: Owner;
  created_at?: string;
  updated_at?: string;
}

export interface File {
  id: number;
  uuid: string;
  original_filename: string;
  filename: string;
  file_size: number;
  mime_type: string;
  status: 'pending' | 'completed' | 'invalid';
  user: {
    id: number;
    name: string;
  };
  created_at?: string;
  updated_at?: string;
}

export interface PaginatedFiles {
  data: File[];
  current_page: number;
  last_page: number;
  per_page: number;
  total: number;
}

export interface SharedData {
  name: string;
  quote: { message: string; author: string };
  auth: Auth;
  organisations: Organisation[] | null;
  currentOrganisation: Organisation | null;
  sidebarOpen: boolean;
  [key: string]: unknown;
}

export interface User {
  id: number;
  name: string;
  email: string;
  avatar?: string;
  email_verified_at: string | null;
  two_factor_enabled?: boolean;
  created_at: string;
  updated_at: string;
  [key: string]: unknown; // This allows for additional properties...
}

export interface PaginatedData<T> {
  data: T[];
  current_page: number;
  first_page_url: string;
  from: number;
  last_page: number;
  last_page_url: string;
  links: {
    active: boolean;
    label: string;
    url: string | null;
  }[];
  next_page_url: string | null;
  path: string;
  per_page: number;
  prev_page_url: string | null;
  to: number;
  total: number;
}
