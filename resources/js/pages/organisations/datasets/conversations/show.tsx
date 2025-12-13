import ChatInput from '@/components/chat-input';
import ChatMessageList from '@/components/chat-message-list';
import AppLayout from '@/layouts/app-layout';
import { store as sendMessage } from '@/routes/api/v1/conversations/messages';
import { dashboard } from '@/routes/organisations';
import { show as datasetShow, index } from '@/routes/organisations/datasets';
import { show as conversationShow } from '@/routes/organisations/datasets/conversations';
import {
  type BreadcrumbItem,
  type Conversation,
  type Dataset,
  type Message,
  type Organisation,
} from '@/types';
import { Head } from '@inertiajs/react';
import { useEffect, useRef, useState } from 'react';

interface ShowProps {
  organisation: Organisation;
  dataset: Dataset;
  conversation: Conversation & {
    messages?: Array<{
      id: number;
      role: string;
      content:
        | string
        | Array<{ type?: string; text?: string; [key: string]: unknown }>
        | { text?: string; [key: string]: unknown };
    }>;
  };
}

export default function ConversationShow({
  organisation,
  dataset,
  conversation,
}: ShowProps) {
  // Transform conversation messages to the expected format
  const transformMessages = (
    conversationMessages?: ShowProps['conversation']['messages'],
  ): Message[] => {
    if (!conversationMessages) {
      return [];
    }

    return conversationMessages.map((msg) => {
      let content = '';
      if (typeof msg.content === 'string') {
        content = msg.content;
      } else if (Array.isArray(msg.content)) {
        // Extract text from content array (Neuron AI format: [{type: 'text', text: '...'}])
        content = msg.content
          .map((part) => {
            if (typeof part === 'object' && part !== null) {
              // Handle Neuron AI format: {type: 'text', text: '...'}
              if ('text' in part && typeof part.text === 'string') {
                return part.text;
              }
              // Fallback for other formats
              return JSON.stringify(part);
            }
            return String(part);
          })
          .join('');
      } else if (
        typeof msg.content === 'object' &&
        msg.content !== null &&
        !Array.isArray(msg.content)
      ) {
        // Handle case where content is a single object with text property
        const contentObj = msg.content as {
          text?: string;
          [key: string]: unknown;
        };
        if ('text' in contentObj && typeof contentObj.text === 'string') {
          content = contentObj.text;
        } else {
          content = JSON.stringify(msg.content);
        }
      }

      return {
        content,
        role: msg.role as 'user' | 'assistant',
      };
    });
  };

  const [messages, setMessages] = useState<Message[]>(() =>
    transformMessages(conversation.messages),
  );
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (content: string) => {
    // Add user message immediately
    const userMessage: Message = { content, role: 'user' };
    setMessages((prev) => [...prev, userMessage]);
    setIsSending(true);

    try {
      // Send message via API
      const response = await fetch(sendMessage(conversation.uuid).url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-TOKEN':
            document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
              ?.content || '',
        },
        body: JSON.stringify({ content }),
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const data = await response.json();

      // Add assistant response
      const assistantMessage: Message = {
        content: data.message.content,
        role: 'assistant',
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      // Remove user message on error
      setMessages((prev) => prev.slice(0, -1));
      alert('Failed to send message. Please try again.');
    } finally {
      setIsSending(false);
    }
  };

  const breadcrumbs: BreadcrumbItem[] = [
    {
      title: 'Organisations',
      href: dashboard(organisation.uuid).url,
    },
    {
      title: organisation.name,
      href: dashboard(organisation.uuid).url,
    },
    {
      title: 'Datasets',
      href: index(organisation.uuid).url,
    },
    {
      title: dataset.name,
      href: datasetShow({
        organisation: organisation.uuid,
        dataset: dataset.uuid,
      }).url,
    },
    {
      title: conversation.title || 'Conversation',
      href: conversationShow({
        organisation: organisation.uuid,
        dataset: dataset.uuid,
        conversation: conversation.uuid,
      }).url,
    },
  ];

  return (
    <AppLayout breadcrumbs={breadcrumbs}>
      <Head title={`Conversation - ${dataset.name} - ${organisation.name}`} />
      <div className="mx-auto flex h-full w-full max-w-4xl flex-1 flex-col overflow-hidden rounded-xl border border-sidebar-border/70 dark:border-sidebar-border">
        <div className="flex flex-1 flex-col overflow-hidden">
          <ChatMessageList messages={messages} />
          <div ref={messagesEndRef} />
        </div>
        <ChatInput onSend={handleSendMessage} disabled={isSending} />
      </div>
    </AppLayout>
  );
}
