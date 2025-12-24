<?php

namespace Database\Factories;

use App\Models\Research;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends \Illuminate\Database\Eloquent\Factories\Factory<\App\Models\ResearchLink>
 */
class ResearchLinkFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'research_id' => Research::factory(),
            'user_id' => User::factory(),
            'url' => fake()->url(),
            'content' => null,
            'summary' => fake()->optional()->paragraph(),
            'status' => 'pending',
        ];
    }
}
