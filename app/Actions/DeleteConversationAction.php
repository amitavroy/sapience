<?php

namespace App\Actions;

use App\Models\Conversation;
use App\Models\Message;
use Illuminate\Support\Facades\DB;

class DeleteConversationAction
{
    /**
     * Delete a conversation and all its associated messages.
     */
    public function execute(Conversation $conversation): void
    {
        DB::transaction(function () use ($conversation) {
            // Delete all messages associated with the conversation
            Message::where('thread_id', $conversation->id)->delete();

            // Delete the conversation
            $conversation->delete();
        });
    }
}
