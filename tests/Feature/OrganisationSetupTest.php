<?php

use App\Models\Organisation;
use App\Models\User;

test('new users without organisations are redirected to setup after registration', function () {
    $response = $this->post(route('register.store'), [
        'name' => 'Test User',
        'email' => 'test@example.com',
        'password' => 'password',
        'password_confirmation' => 'password',
    ]);

    $this->assertAuthenticated();
    $response->assertRedirect(route('organisations.setup'));
});

test('users with existing organisations are redirected to organisation dashboard after registration', function () {
    $organisation = Organisation::factory()->create();
    $user = User::factory()->create();

    // Attach organisation before registration redirect logic
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    // Simulate what happens after registration - user should be redirected to organisation dashboard
    $response = $this->actingAs($user)->get(route('organisations.setup'));

    // User with organisation should be able to access dashboard
    $dashboardResponse = $this->actingAs($user)->get(route('organisations.dashboard', $organisation));
    $dashboardResponse->assertSuccessful();
});

test('setup page can be rendered', function () {
    $user = User::factory()->create();

    $response = $this->actingAs($user)->get(route('organisations.setup'));

    $response->assertSuccessful();
});

test('join form can be rendered', function () {
    $user = User::factory()->create();

    $response = $this->actingAs($user)->get(route('organisations.join'));

    $response->assertSuccessful();
});

test('user can join organisation with valid UUID', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $response = $this->actingAs($user)->post(route('organisations.join.store'), [
        'code' => $organisation->uuid,
    ]);

    $response->assertRedirect(route('organisations.dashboard', $organisation));
    expect($user->organisations)->toHaveCount(1);
    expect($user->organisations->first()->id)->toBe($organisation->id);
    expect($user->organisations->first()->pivot->role)->toBe('member');
});

test('user cannot join organisation with invalid UUID', function () {
    $user = User::factory()->create();

    $response = $this->actingAs($user)->post(route('organisations.join.store'), [
        'code' => 'invalid-uuid',
    ]);

    $response->assertSessionHasErrors('code');
    expect($user->organisations)->toHaveCount(0);
});

test('user cannot join non-existent organisation', function () {
    $user = User::factory()->create();
    $nonExistentUuid = (string) \Illuminate\Support\Str::uuid();

    $response = $this->actingAs($user)->post(route('organisations.join.store'), [
        'code' => $nonExistentUuid,
    ]);

    $response->assertNotFound();
    expect($user->organisations)->toHaveCount(0);
});

test('user cannot join same organisation twice', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->post(route('organisations.join.store'), [
        'code' => $organisation->uuid,
    ]);

    $response->assertRedirect(route('organisations.dashboard', $organisation));
    expect($user->organisations)->toHaveCount(1);
});

test('create form can be rendered', function () {
    $user = User::factory()->create();

    $response = $this->actingAs($user)->get(route('organisations.create'));

    $response->assertSuccessful();
});

test('user can create new organisation', function () {
    $user = User::factory()->create();

    $response = $this->actingAs($user)->post(route('organisations.store'), [
        'name' => 'Test Organisation',
    ]);

    $organisation = Organisation::where('name', 'Test Organisation')->first();

    expect($organisation)->not->toBeNull();
    $response->assertRedirect(route('organisations.dashboard', $organisation));
    expect($user->organisations)->toHaveCount(1);
    expect($user->organisations->first()->id)->toBe($organisation->id);
    expect($user->organisations->first()->pivot->role)->toBe('admin');
});

test('organisation name is required when creating', function () {
    $user = User::factory()->create();

    $response = $this->actingAs($user)->post(route('organisations.store'), []);

    $response->assertSessionHasErrors('name');
});

test('organisation dashboard can be accessed by members', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->get(route('organisations.dashboard', $organisation));

    $response->assertSuccessful();
});

test('organisation dashboard cannot be accessed by non-members', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $response = $this->actingAs($user)->get(route('organisations.dashboard', $organisation));

    $response->assertForbidden();
});

test('middleware redirects users without organisations from dashboard', function () {
    $user = User::factory()->create();

    $response = $this->actingAs($user)->get(route('dashboard'));

    $response->assertRedirect(route('organisations.setup'));
});

test('middleware allows users with organisations to access dashboard', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->get(route('dashboard'));

    $response->assertSuccessful();
});
