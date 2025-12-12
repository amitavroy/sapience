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
  conversation: Conversation;
}

export default function ConversationShow({
  organisation,
  dataset,
  conversation,
}: ShowProps) {
  const [messages, setMessages] = useState<Message[]>([]);
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
      <div className="flex h-full flex-1 flex-col overflow-hidden rounded-xl border border-sidebar-border/70 dark:border-sidebar-border">
        <div className="flex flex-1 flex-col overflow-hidden">
          <ChatMessageList messages={messages} />
          <div ref={messagesEndRef} />
        </div>
        <ChatInput onSend={handleSendMessage} disabled={isSending} />
      </div>
    </AppLayout>
  );
}
