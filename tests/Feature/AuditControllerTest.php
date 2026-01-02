<?php

use App\Models\Audit;
use App\Models\Organisation;
use App\Models\User;

test('user can view audits index for their organisation', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $audit1 = Audit::factory()->create([
        'organisation_id' => $organisation->id,
        'user_id' => $user->id,
    ]);
    $audit2 = Audit::factory()->create([
        'organisation_id' => $organisation->id,
        'user_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->get(
        route('organisations.audits.index', $organisation)
    );

    $response->assertSuccessful();
    $response->assertInertia(
        fn ($page) => $page
            ->component('organisations/audits/index')
            ->has('audits.data', 2)
            ->where('organisation.id', $organisation->id)
    );
});

test('user cannot view audits for organisation they do not belong to', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $response = $this->actingAs($user)->get(
        route('organisations.audits.index', $organisation)
    );

    $response->assertForbidden();
});

test('user can access create audit page for their organisation', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->get(
        route('organisations.audits.create', $organisation)
    );

    $response->assertSuccessful();
    $response->assertInertia(
        fn ($page) => $page
            ->component('organisations/audits/create')
            ->where('organisation.id', $organisation->id)
    );
});

test('user cannot access create audit page for organisation they do not belong to', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $response = $this->actingAs($user)->get(
        route('organisations.audits.create', $organisation)
    );

    $response->assertForbidden();
});

test('member can create an audit', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->post(
        route('organisations.audits.store', $organisation),
        [
            'website_url' => 'https://example.com',
        ]
    );

    $response->assertRedirect();
    $response->assertSessionHas('success');

    $this->assertDatabaseHas('audits', [
        'website_url' => 'https://example.com',
        'organisation_id' => $organisation->id,
        'user_id' => $user->id,
        'status' => 'pending',
    ]);
});

test('admin can create an audit', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $response = $this->actingAs($user)->post(
        route('organisations.audits.store', $organisation),
        [
            'website_url' => 'https://example.com',
        ]
    );

    $response->assertRedirect();
    $response->assertSessionHas('success');

    $this->assertDatabaseHas('audits', [
        'website_url' => 'https://example.com',
        'organisation_id' => $organisation->id,
        'user_id' => $user->id,
        'status' => 'pending',
    ]);
});

test('user cannot create audit for organisation they do not belong to', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $response = $this->actingAs($user)->post(
        route('organisations.audits.store', $organisation),
        [
            'website_url' => 'https://example.com',
        ]
    );

    $response->assertForbidden();
    $this->assertDatabaseMissing('audits', [
        'website_url' => 'https://example.com',
    ]);
});

test('audit creation requires website_url', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->post(
        route('organisations.audits.store', $organisation),
        []
    );

    $response->assertSessionHasErrors('website_url');
});

test('audit creation requires website_url to be a valid URL', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->post(
        route('organisations.audits.store', $organisation),
        [
            'website_url' => 'not-a-valid-url',
        ]
    );

    $response->assertSessionHasErrors('website_url');
});

test('audit creation requires website_url to be a string', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->post(
        route('organisations.audits.store', $organisation),
        [
            'website_url' => 12345,
        ]
    );

    $response->assertSessionHasErrors('website_url');
});

test('audit creation requires website_url to not exceed max length', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $longUrl = 'https://example.com/'.str_repeat('a', 256);

    $response = $this->actingAs($user)->post(
        route('organisations.audits.store', $organisation),
        [
            'website_url' => $longUrl,
        ]
    );

    $response->assertSessionHasErrors('website_url');
});

test('audit creation accepts valid URLs', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $validUrls = [
        'https://example.com',
        'http://example.com',
        'https://www.example.com',
        'https://example.com/path',
        'https://example.com/path?query=value',
        'https://subdomain.example.com',
    ];

    foreach ($validUrls as $url) {
        $response = $this->actingAs($user)->post(
            route('organisations.audits.store', $organisation),
            [
                'website_url' => $url,
            ]
        );

        $response->assertRedirect();
        $response->assertSessionHas('success');

        $this->assertDatabaseHas('audits', [
            'website_url' => $url,
            'organisation_id' => $organisation->id,
            'user_id' => $user->id,
        ]);
    }
});

test('audit creation sets logged in user as creator', function () {
    $user1 = User::factory()->create();
    $user2 = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user1->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user1)->post(
        route('organisations.audits.store', $organisation),
        [
            'website_url' => 'https://example.com',
        ]
    );

    $response->assertRedirect();

    $this->assertDatabaseHas('audits', [
        'website_url' => 'https://example.com',
        'user_id' => $user1->id,
    ]);

    $this->assertDatabaseMissing('audits', [
        'website_url' => 'https://example.com',
        'user_id' => $user2->id,
    ]);
});
