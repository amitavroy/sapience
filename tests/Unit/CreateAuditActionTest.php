<?php

use App\Actions\Audit\CreateAuditAction;
use App\Enums\AuditStatus;
use App\Models\Audit;
use App\Models\Organisation;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

uses(TestCase::class, RefreshDatabase::class);

test('creates an audit with correct attributes', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $action = new CreateAuditAction;

    $validated = [
        'website_url' => 'https://example.com',
    ];

    $audit = $action->execute($validated, $organisation, $user);

    expect($audit)->toBeInstanceOf(Audit::class);
    expect($audit->website_url)->toBe('https://example.com');
    expect($audit->organisation_id)->toBe($organisation->id);
    expect($audit->user_id)->toBe($user->id);
    expect($audit->status)->toBe(AuditStatus::Pending);
    expect($audit->report)->toBeNull();
    expect($audit->exists)->toBeTrue();
});

test('creates an audit with status set to pending by default', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $action = new CreateAuditAction;

    $validated = [
        'website_url' => 'https://test.com',
    ];

    $audit = $action->execute($validated, $organisation, $user);

    expect($audit->status)->toBe(AuditStatus::Pending);
});

test('creates an audit with correct user and organisation relationships', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $action = new CreateAuditAction;

    $validated = [
        'website_url' => 'https://example.com',
    ];

    $audit = $action->execute($validated, $organisation, $user);

    expect($audit->user_id)->toBe($user->id);
    expect($audit->organisation_id)->toBe($organisation->id);
    expect($audit->user)->toBeInstanceOf(User::class);
    expect($audit->user->id)->toBe($user->id);
    expect($audit->organisation)->toBeInstanceOf(Organisation::class);
    expect($audit->organisation->id)->toBe($organisation->id);
});

test('creates multiple audits for the same organisation', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $action = new CreateAuditAction;

    $audit1 = $action->execute(['website_url' => 'https://example1.com'], $organisation, $user);
    $audit2 = $action->execute(['website_url' => 'https://example2.com'], $organisation, $user);

    expect($audit1->id)->not->toBe($audit2->id);
    expect($audit1->organisation_id)->toBe($organisation->id);
    expect($audit2->organisation_id)->toBe($organisation->id);
    expect($audit1->user_id)->toBe($user->id);
    expect($audit2->user_id)->toBe($user->id);
});

test('creates audits for different users in the same organisation', function () {
    $user1 = User::factory()->create();
    $user2 = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $action = new CreateAuditAction;

    $audit1 = $action->execute(['website_url' => 'https://example.com'], $organisation, $user1);
    $audit2 = $action->execute(['website_url' => 'https://example.com'], $organisation, $user2);

    expect($audit1->user_id)->toBe($user1->id);
    expect($audit2->user_id)->toBe($user2->id);
    expect($audit1->organisation_id)->toBe($organisation->id);
    expect($audit2->organisation_id)->toBe($organisation->id);
});
