<?php

use App\Models\Organisation;
use App\Models\User;

test('guests are redirected to the login page', function () {
    $this->get(route('dashboard'))->assertRedirect(route('login'));
});

test('authenticated users without organisations are redirected to setup', function () {
    $this->actingAs($user = User::factory()->create());

    $this->get(route('dashboard'))->assertRedirect(route('organisations.setup'));
});

test('authenticated users with organisations can visit the dashboard', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $this->actingAs($user);

    $this->get(route('dashboard'))->assertOk();
});
