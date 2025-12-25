<?php

use App\Actions\CreateConversationAction;
use App\Models\Conversation;
use App\Models\Dataset;
use App\Models\Organisation;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

uses(TestCase::class, RefreshDatabase::class);

test('creates a conversation with correct attributes', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $action = new CreateConversationAction;
    $conversation = $action->execute($organisation, $dataset, $user);

    expect($conversation)->toBeInstanceOf(Conversation::class);
    expect($conversation->title)->toBeNull();
    expect($conversation->user_id)->toBe($user->id);
    expect($conversation->organisation_id)->toBe($organisation->id);
    expect($conversation->dataset_id)->toBe($dataset->id);
    expect($conversation->exists)->toBeTrue();
});
