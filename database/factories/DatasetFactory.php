<?php

namespace Database\Factories;

use App\Models\Organisation;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;
use Illuminate\Support\Str;

/**
 * @extends \Illuminate\Database\Eloquent\Factories\Factory<\App\Models\Dataset>
 */
class DatasetFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'uuid' => (string) Str::uuid(),
            'name' => fake()->words(3, true),
            'description' => fake()->paragraph(),
            'is_active' => fake()->boolean(90),
            'owner_id' => User::factory(),
            'organisation_id' => Organisation::factory(),
        ];
    }
}
