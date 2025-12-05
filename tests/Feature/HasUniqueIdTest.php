<?php

use App\Models\Organisation;
use Illuminate\Support\Str;

test('trait auto-generates uuid on model creation', function () {
    $organisation = Organisation::factory()->create(['uuid' => null]);

    expect($organisation->uuid)->not->toBeNull();
    expect($organisation->uuid)->toBeString();
    expect($organisation->uuid)->toMatch('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i');
});

test('trait does not overwrite uuid if already set', function () {
    $customUuid = (string) Str::uuid();
    $organisation = new Organisation(['name' => 'Test Org', 'uuid' => $customUuid]);
    $organisation->save();

    expect($organisation->uuid)->toBe($customUuid);
});

test('trait sets route key name to uuid', function () {
    $organisation = Organisation::factory()->create();

    expect($organisation->getRouteKeyName())->toBe('uuid');
});

test('trait adds uuid to fillable attributes', function () {
    $organisation = new Organisation;
    $fillable = $organisation->getFillable();

    expect($fillable)->toContain('uuid');
});

test('trait merge fillable does not duplicate uuid', function () {
    $organisation = new Organisation;
    $fillable = $organisation->getFillable();

    $uuidCount = array_count_values($fillable)['uuid'] ?? 0;
    expect($uuidCount)->toBe(1);
});
