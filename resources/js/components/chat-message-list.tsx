import { MarkdownContent } from '@/components/markdown-content';
import { type Message } from '@/types';

interface ChatMessageListProps {
  messages: Message[];
}

export default function ChatMessageList({ messages }: ChatMessageListProps) {
  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
      {messages.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-muted-foreground">
            Start a conversation by sending a message.
          </p>
        </div>
      ) : (
        messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                message.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground'
              }`}
            >
              {message.role === 'user' ? (
                <p className="break-words whitespace-pre-wrap">
                  {message.content}
                </p>
              ) : (
                <MarkdownContent
                  content={message.content}
                  className="[&_*]:text-muted-foreground [&_a]:text-blue-600 [&_a]:underline [&_a]:dark:text-blue-400"
                />
              )}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
