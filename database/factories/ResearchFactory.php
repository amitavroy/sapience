<?php

namespace Database\Factories;

use App\Models\Organisation;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends \Illuminate\Database\Eloquent\Factories\Factory<\App\Models\Research>
 */
class ResearchFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'user_id' => User::factory(),
            'organisation_id' => Organisation::factory(),
            'query' => fake()->sentence(),
            'instructions' => fake()->optional()->paragraph(),
            'report' => fake()->optional()->text(2000),
            'status' => 'pending',
        ];
    }
}
