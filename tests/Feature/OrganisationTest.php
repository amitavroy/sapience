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

test('select page can be rendered for users with multiple organisations', function () {
    $user = User::factory()->create();
    $organisation1 = Organisation::factory()->create();
    $organisation2 = Organisation::factory()->create();
    $user->organisations()->attach($organisation1->id, ['role' => 'member']);
    $user->organisations()->attach($organisation2->id, ['role' => 'member']);

    $response = $this->actingAs($user)->get(route('organisations.select'));

    $response->assertSuccessful();
});

test('select page redirects to setup if user has no organisations', function () {
    $user = User::factory()->create();

    $response = $this->actingAs($user)->get(route('organisations.select'));

    $response->assertRedirect(route('organisations.setup'));
});

test('select page redirects to dashboard if user has only one organisation', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->get(route('organisations.select'));

    $response->assertRedirect(route('organisations.dashboard', $organisation));
    expect($user->fresh()->last_organisation_id)->toBe($organisation->id);
});

test('user can select an organisation', function () {
    $user = User::factory()->create();
    $organisation1 = Organisation::factory()->create();
    $organisation2 = Organisation::factory()->create();
    $user->organisations()->attach($organisation1->id, ['role' => 'member']);
    $user->organisations()->attach($organisation2->id, ['role' => 'member']);

    $response = $this->actingAs($user)->post(route('organisations.select.store'), [
        'organisation_id' => $organisation1->id,
    ]);

    $response->assertRedirect(route('organisations.dashboard', $organisation1));
    expect($user->fresh()->last_organisation_id)->toBe($organisation1->id);
});

test('user cannot select an organisation they do not belong to', function () {
    $user = User::factory()->create();
    $organisation1 = Organisation::factory()->create();
    $organisation2 = Organisation::factory()->create();
    $user->organisations()->attach($organisation1->id, ['role' => 'member']);

    $response = $this->actingAs($user)->post(route('organisations.select.store'), [
        'organisation_id' => $organisation2->id,
    ]);

    $response->assertSessionHasErrors('organisation_id');
});

test('organisation_id is required when selecting', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->post(route('organisations.select.store'), []);

    $response->assertSessionHasErrors('organisation_id');
});

test('dashboard access updates last_organisation_id', function () {
    $user = User::factory()->create();
    $organisation1 = Organisation::factory()->create();
    $organisation2 = Organisation::factory()->create();
    $user->organisations()->attach($organisation1->id, ['role' => 'member']);
    $user->organisations()->attach($organisation2->id, ['role' => 'member']);

    expect($user->last_organisation_id)->toBeNull();

    $response = $this->actingAs($user)->get(route('organisations.dashboard', $organisation1));

    $response->assertSuccessful();
    expect($user->fresh()->last_organisation_id)->toBe($organisation1->id);
});

test('dashboard access updates last_organisation_id when switching organisations', function () {
    $user = User::factory()->create([
        'last_organisation_id' => null,
    ]);
    $organisation1 = Organisation::factory()->create();
    $organisation2 = Organisation::factory()->create();
    $user->organisations()->attach($organisation1->id, ['role' => 'member']);
    $user->organisations()->attach($organisation2->id, ['role' => 'member']);

    // Access first organisation
    $this->actingAs($user)->get(route('organisations.dashboard', $organisation1));
    expect($user->fresh()->last_organisation_id)->toBe($organisation1->id);

    // Access second organisation
    $this->actingAs($user)->get(route('organisations.dashboard', $organisation2));
    expect($user->fresh()->last_organisation_id)->toBe($organisation2->id);
});

test('organisations are shared in Inertia props', function () {
    $user = User::factory()->create();
    $organisation1 = Organisation::factory()->create();
    $organisation2 = Organisation::factory()->create();
    $user->organisations()->attach($organisation1->id, ['role' => 'member']);
    $user->organisations()->attach($organisation2->id, ['role' => 'member']);

    $response = $this->actingAs($user)->get(route('organisations.dashboard', $organisation1));

    $response->assertSuccessful();
    $response->assertInertia(fn ($page) => $page
        ->has('organisations', 2)
        ->where('currentOrganisation.id', $organisation1->id)
    );
});

test('current organisation is null when user has no last_organisation_id and not on organisation route', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->get(route('dashboard'));

    $response->assertSuccessful();
    $response->assertInertia(fn ($page) => $page
        ->has('organisations', 1)
        ->where('currentOrganisation', null)
    );
});

test('current organisation is set from last_organisation_id when not on organisation route', function () {
    $user = User::factory()->create();
    $organisation1 = Organisation::factory()->create();
    $organisation2 = Organisation::factory()->create();
    $user->organisations()->attach($organisation1->id, ['role' => 'member']);
    $user->organisations()->attach($organisation2->id, ['role' => 'member']);
    $user->update(['last_organisation_id' => $organisation1->id]);

    $response = $this->actingAs($user)->get(route('dashboard'));

    $response->assertSuccessful();
    $response->assertInertia(fn ($page) => $page
        ->has('organisations', 2)
        ->where('currentOrganisation.id', $organisation1->id)
    );
});
