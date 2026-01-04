import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownContentProps {
  content: string;
  className?: string;
}

export function MarkdownContent({
  content,
  className = '',
}: MarkdownContentProps) {
  return (
    <div
      className={`prose prose-sm dark:prose-invert max-w-none [&_a]:text-blue-600 [&_a]:underline [&_a]:dark:text-blue-400 [&_h1]:mt-8 [&_h1]:mb-4 [&_h1]:text-3xl [&_h1]:font-bold [&_h2]:mt-6 [&_h2]:mb-3 [&_h2]:text-2xl [&_h2]:font-bold [&_h3]:mt-5 [&_h3]:mb-3 [&_h3]:text-xl [&_h3]:font-bold [&_h4]:mt-4 [&_h4]:mb-2 [&_h4]:text-lg [&_h4]:font-bold [&_h5]:mt-3 [&_h5]:mb-2 [&_h5]:text-base [&_h5]:font-bold [&_h6]:mt-2 [&_h6]:mb-2 [&_h6]:text-sm [&_h6]:font-bold [&_li]:my-1 [&_ol]:my-4 [&_ol]:ml-6 [&_ol]:list-decimal [&_pre]:overflow-y-auto [&_pre]:bg-muted/50 [&_pre]:py-8 [&_pre]:font-mono [&_table]:my-4 [&_table]:w-full [&_table]:border-collapse [&_table]:border [&_table]:border-border [&_td]:border [&_td]:border-border [&_td]:px-4 [&_td]:py-2 [&_th]:border [&_th]:border-border [&_th]:bg-muted [&_th]:px-4 [&_th]:py-2 [&_th]:text-left [&_th]:font-semibold [&_tr:nth-child(even)]:bg-muted/50 [&_ul]:my-4 [&_ul]:ml-6 [&_ul]:list-disc ${className}`}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
