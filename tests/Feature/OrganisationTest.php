<?php

use App\Models\Organisation;
use App\Models\User;

test('organisation can be created with uuid and name', function () {
    $organisation = Organisation::factory()->create([
        'name' => 'Test Organisation',
    ]);

    expect($organisation->name)->toBe('Test Organisation');
    expect($organisation->uuid)->not->toBeNull();
    expect($organisation->uuid)->toBeString();
});

test('organisation uuid is unique', function () {
    $uuid = (string) \Illuminate\Support\Str::uuid();

    Organisation::factory()->create(['uuid' => $uuid]);

    expect(fn () => Organisation::factory()->create(['uuid' => $uuid]))
        ->toThrow(\Illuminate\Database\QueryException::class);
});

test('user can belong to multiple organisations', function () {
    $user = User::factory()->create();
    $organisation1 = Organisation::factory()->create();
    $organisation2 = Organisation::factory()->create();

    $user->organisations()->attach($organisation1->id, ['role' => 'admin']);
    $user->organisations()->attach($organisation2->id, ['role' => 'member']);

    expect($user->organisations)->toHaveCount(2);
    expect($user->organisations->pluck('id')->toArray())->toContain($organisation1->id, $organisation2->id);
});

test('organisation can have multiple users', function () {
    $organisation = Organisation::factory()->create();
    $user1 = User::factory()->create();
    $user2 = User::factory()->create();

    $organisation->users()->attach($user1->id, ['role' => 'admin']);
    $organisation->users()->attach($user2->id, ['role' => 'member']);

    expect($organisation->users)->toHaveCount(2);
    expect($organisation->users->pluck('id')->toArray())->toContain($user1->id, $user2->id);
});

test('pivot table stores role correctly', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $pivot = $user->organisations()->first()->pivot;
    expect($pivot->role)->toBe('admin');
});

test('relationships work bidirectionally', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    expect($user->organisations->first()->id)->toBe($organisation->id);
    expect($organisation->users->first()->id)->toBe($user->id);
});

test('user cannot be attached to same organisation twice', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    expect(fn () => $user->organisations()->attach($organisation->id, ['role' => 'member']))
        ->toThrow(\Illuminate\Database\QueryException::class);
});

test('pivot table includes timestamps', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $pivot = $user->organisations()->first()->pivot;
    expect($pivot->created_at)->not->toBeNull();
    expect($pivot->updated_at)->not->toBeNull();
});

test('organisation uses uuid for route model binding', function () {
    $organisation = Organisation::factory()->create();

    expect($organisation->getRouteKeyName())->toBe('uuid');
    expect(Organisation::where('uuid', $organisation->uuid)->first()->id)->toBe($organisation->id);
});

test('organisation uuid is auto-generated on create', function () {
    $organisation = new Organisation(['name' => 'Test Org']);
    $organisation->save();

    expect($organisation->uuid)->not->toBeNull();
    expect($organisation->uuid)->toBeString();
    expect($organisation->uuid)->toMatch('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i');
});

test('organisation uuid is not overwritten if already set', function () {
    $customUuid = (string) \Illuminate\Support\Str::uuid();
    $organisation = new Organisation(['name' => 'Test Org', 'uuid' => $customUuid]);
    $organisation->save();

    expect($organisation->uuid)->toBe($customUuid);
});
