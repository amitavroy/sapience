<?php

use App\Models\Conversation;
use App\Models\Dataset;
use App\Models\Organisation;
use App\Models\User;
use Illuminate\Support\Str;

test('conversation can be created with uuid and required fields', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $conversation = Conversation::factory()->create([
        'title' => null,
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);

    expect($conversation->title)->toBeNull();
    expect($conversation->uuid)->not->toBeNull();
    expect($conversation->uuid)->toBeString();
    expect($conversation->user_id)->toBe($user->id);
    expect($conversation->organisation_id)->toBe($organisation->id);
    expect($conversation->dataset_id)->toBe($dataset->id);
});

test('conversation uuid is unique', function () {
    $uuid = (string) Str::uuid();
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    Conversation::factory()->create([
        'uuid' => $uuid,
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);

    expect(fn () => Conversation::factory()->create([
        'uuid' => $uuid,
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]))->toThrow(\Illuminate\Database\QueryException::class);
});

test('conversation belongs to user', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $conversation = Conversation::factory()->create([
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);

    expect($conversation->user)->toBeInstanceOf(User::class);
    expect($conversation->user->id)->toBe($user->id);
    expect($conversation->user_id)->toBe($user->id);
});

test('conversation belongs to organisation', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $conversation = Conversation::factory()->create([
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);

    expect($conversation->organisation)->toBeInstanceOf(Organisation::class);
    expect($conversation->organisation->id)->toBe($organisation->id);
    expect($conversation->organisation_id)->toBe($organisation->id);
});

test('conversation belongs to dataset', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $conversation = Conversation::factory()->create([
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);

    expect($conversation->dataset)->toBeInstanceOf(Dataset::class);
    expect($conversation->dataset->id)->toBe($dataset->id);
    expect($conversation->dataset_id)->toBe($dataset->id);
});

test('user has many conversations', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $conversation1 = Conversation::factory()->create([
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);
    $conversation2 = Conversation::factory()->create([
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);

    expect($user->conversations)->toHaveCount(2);
    expect($user->conversations->pluck('id')->toArray())->toContain($conversation1->id, $conversation2->id);
});

test('organisation has many conversations', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $conversation1 = Conversation::factory()->create([
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);
    $conversation2 = Conversation::factory()->create([
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);

    expect($organisation->conversations)->toHaveCount(2);
    expect($organisation->conversations->pluck('id')->toArray())->toContain($conversation1->id, $conversation2->id);
});

test('dataset has many conversations', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $conversation1 = Conversation::factory()->create([
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);
    $conversation2 = Conversation::factory()->create([
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);

    expect($dataset->conversations)->toHaveCount(2);
    expect($dataset->conversations->pluck('id')->toArray())->toContain($conversation1->id, $conversation2->id);
});

test('conversation uses uuid for route model binding', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $conversation = Conversation::factory()->create([
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);

    expect($conversation->getRouteKeyName())->toBe('uuid');
    expect(Conversation::where('uuid', $conversation->uuid)->first()->id)->toBe($conversation->id);
});

test('conversation uuid is auto-generated on create', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $conversation = new Conversation([
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);
    $conversation->save();

    expect($conversation->uuid)->not->toBeNull();
    expect($conversation->uuid)->toBeString();
    expect($conversation->uuid)->toMatch('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i');
});

test('conversation uuid is not overwritten if already set', function () {
    $customUuid = (string) Str::uuid();
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $conversation = new Conversation([
        'uuid' => $customUuid,
        'user_id' => $user->id,
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
    ]);
    $conversation->save();

    expect($conversation->uuid)->toBe($customUuid);
});
