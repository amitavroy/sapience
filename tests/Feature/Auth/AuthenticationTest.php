<?php

use App\Models\Organisation;
use App\Models\User;
use Illuminate\Support\Facades\RateLimiter;
use Laravel\Fortify\Features;

test('login screen can be rendered', function () {
    $response = $this->get(route('login'));

    $response->assertStatus(200);
});

test('users can authenticate using the login screen', function () {
    $user = User::factory()->withoutTwoFactor()->create();

    $response = $this->post(route('login.store'), [
        'email' => $user->email,
        'password' => 'password',
    ]);

    $this->assertAuthenticated();
    $response->assertRedirect(route('organisations.setup', absolute: false));
});

test('users with no organisations are redirected to setup after login', function () {
    $user = User::factory()->withoutTwoFactor()->create();

    $response = $this->post(route('login.store'), [
        'email' => $user->email,
        'password' => 'password',
    ]);

    $this->assertAuthenticated();
    $response->assertRedirect(route('organisations.setup', absolute: false));
});

test('users with last_organisation_id are redirected to that organisation dashboard after login', function () {
    $organisation = Organisation::factory()->create();
    $user = User::factory()->withoutTwoFactor()->create([
        'last_organisation_id' => $organisation->id,
    ]);
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->post(route('login.store'), [
        'email' => $user->email,
        'password' => 'password',
    ]);

    $this->assertAuthenticated();
    $response->assertRedirect(route('organisations.dashboard', $organisation, absolute: false));
});

test('users with single organisation are redirected to dashboard and last_organisation_id is set after login', function () {
    $organisation = Organisation::factory()->create();
    $user = User::factory()->withoutTwoFactor()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->post(route('login.store'), [
        'email' => $user->email,
        'password' => 'password',
    ]);

    $this->assertAuthenticated();
    $response->assertRedirect(route('organisations.dashboard', $organisation, absolute: false));
    expect($user->fresh()->last_organisation_id)->toBe($organisation->id);
});

test('users with multiple organisations and no last_organisation_id are redirected to select after login', function () {
    $organisation1 = Organisation::factory()->create();
    $organisation2 = Organisation::factory()->create();
    $user = User::factory()->withoutTwoFactor()->create();
    $user->organisations()->attach($organisation1->id, ['role' => 'member']);
    $user->organisations()->attach($organisation2->id, ['role' => 'member']);

    $response = $this->post(route('login.store'), [
        'email' => $user->email,
        'password' => 'password',
    ]);

    $this->assertAuthenticated();
    $response->assertRedirect(route('organisations.select', absolute: false));
});

test('users with two factor enabled are redirected to two factor challenge', function () {
    if (! Features::canManageTwoFactorAuthentication()) {
        $this->markTestSkipped('Two-factor authentication is not enabled.');
    }

    Features::twoFactorAuthentication([
        'confirm' => true,
        'confirmPassword' => true,
    ]);

    $user = User::factory()->create();

    $user->forceFill([
        'two_factor_secret' => encrypt('test-secret'),
        'two_factor_recovery_codes' => encrypt(json_encode(['code1', 'code2'])),
        'two_factor_confirmed_at' => now(),
    ])->save();

    $response = $this->post(route('login'), [
        'email' => $user->email,
        'password' => 'password',
    ]);

    $response->assertRedirect(route('two-factor.login'));
    $response->assertSessionHas('login.id', $user->id);
    $this->assertGuest();
});

test('users can not authenticate with invalid password', function () {
    $user = User::factory()->create();

    $this->post(route('login.store'), [
        'email' => $user->email,
        'password' => 'wrong-password',
    ]);

    $this->assertGuest();
});

test('users can logout', function () {
    $user = User::factory()->create();

    $response = $this->actingAs($user)->post(route('logout'));

    $this->assertGuest();
    $response->assertRedirect(route('home'));
});

test('users are rate limited', function () {
    $user = User::factory()->create();

    RateLimiter::increment(md5('login'.implode('|', [$user->email, '127.0.0.1'])), amount: 5);

    $response = $this->post(route('login.store'), [
        'email' => $user->email,
        'password' => 'wrong-password',
    ]);

    $response->assertTooManyRequests();
});
