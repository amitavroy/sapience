<?php

namespace App\Actions;

use App\Models\Conversation;
use App\Models\Dataset;
use App\Models\Organisation;
use App\Models\User;

class CreateConversationAction
{
    /**
     * Create a new conversation.
     */
    public function execute(Organisation $organisation, Dataset $dataset, User $user): Conversation
    {
        return Conversation::create([
            'title' => null,
            'user_id' => $user->id,
            'organisation_id' => $organisation->id,
            'dataset_id' => $dataset->id,
        ]);
    }
}
