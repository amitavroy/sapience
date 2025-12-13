<?php

namespace App\Jobs;

use App\Models\Conversation;
use App\Neuron\ConversationTitleAgent;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Log;
use NeuronAI\Chat\Messages\UserMessage;

class CreateConversationTitle implements ShouldQueue
{
    use Queueable;

    /**
     * Create a new job instance.
     */
    public function __construct(
        public int $conversationId
    ) {
        //
    }

    /**
     * Execute the job.
     */
    public function handle(): void
    {
        $conversation = Conversation::findOrFail($this->conversationId);

        // Get the first user message
        $firstUserMessage = $conversation->messages()
            ->where('role', 'user')
            ->orderBy('id', 'asc')
            ->first();

        if (! $firstUserMessage) {
            logger('No first user message found');

            return;
        }

        // Get the system message from the conversation
        $systemMessage = $conversation->messages()
            ->where('role', 'assistant')
            ->orderBy('id', 'asc')
            ->first();

        if (! $systemMessage) {
            logger('No system message found');

            return;
        }

        // Generate title based on conversation, first user message, and system message
        Log::info('Generating title based on conversation, first user message, and system message', [
            'conversation' => $conversation->id,
            'first_user_message' => $firstUserMessage->id,
            'system_message' => $systemMessage->id,
        ]);

        $title = (string) ConversationTitleAgent::make()
            ->chat(new UserMessage(
                'Generate a title for the conversation based on the first user message and the system message.'.
                'The first user message is: '.$firstUserMessage->content.
                'The assistant message is: '.$systemMessage->content
            ))->getContent();

        $conversation->update([
            'title' => $title,
        ]);

        Log::info('Conversation title updated', [
            'conversation' => $conversation->id,
            'title' => $title,
        ]);
    }
}
