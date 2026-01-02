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
  instructions: string | null;
  output_instructions: string | null;
  is_active: boolean;
  files_count: number;
  conversations_count?: number;
  owner: Owner;
  created_at?: string;
  updated_at?: string;
}

export interface Conversation {
  id: number;
  uuid: string;
  title: string | null;
  organisation: Organisation;
  dataset: Dataset;
  user: User;
  created_at?: string;
  updated_at?: string;
}

export interface ResearchLink {
  id: number;
  research_id: number;
  user_id: number;
  url: string;
  content: unknown;
  summary: string | null;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface Research {
  id: number;
  uuid: string;
  query: string;
  instructions: string | null;
  report?: string | null;
  status: 'pending' | 'processing' | 'awaiting_feedback' | 'completed' | 'failed';
  interruption_data?: {
    topic: string;
    search_terms: string[];
    question: string;
    generated_at: string;
  } | null;
  workflow_id?: string | null;
  user: User;
  organisation: Organisation;
  research_links?: ResearchLink[];
  created_at?: string;
  updated_at?: string;
}

export interface AuditLink {
  id: number;
  audit_id: number;
  user_id: number;
  url: string;
  title: string | null;
  content: string | null;
  summary: string | null;
  search_term: string;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface Audit {
  id: number;
  user_id: number;
  organisation_id: number;
  website_url: string;
  status: 'pending' | 'in_progress' | 'summarised' | 'completed' | 'failed';
  analysis: string | null;
  report: string | null;
  created_at?: string;
  updated_at?: string;
  user?: User;
  organisation?: Organisation;
  audit_links?: AuditLink[];
}

export interface Message {
  content: string;
  role: 'user' | 'assistant';
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
