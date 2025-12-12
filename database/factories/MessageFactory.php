<?php

namespace Database\Factories;

use App\Models\Conversation;
use App\Models\Dataset;
use App\Models\Organisation;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends \Illuminate\Database\Eloquent\Factories\Factory<\App\Models\Message>
 */
class MessageFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        $role = fake()->randomElement(['user', 'assistant']);

        return [
            'thread_id' => fn (array $attributes) => $attributes['thread_id'] ?? Conversation::factory()->create()->uuid,
            'organisation_id' => fn (array $attributes) => $attributes['organisation_id'] ?? Organisation::factory(),
            'dataset_id' => fn (array $attributes) => $attributes['dataset_id'] ?? Dataset::factory(),
            'user_id' => fn (array $attributes) => $attributes['user_id'] ?? User::factory(),
            'role' => $role,
            'content' => [
                'text' => fake()->paragraph(),
            ],
            'meta' => $role === 'assistant' ? [
                'model' => fake()->randomElement(['gpt-4', 'gpt-3.5-turbo', 'claude-3-opus', 'claude-3-sonnet']),
            ] : null,
            'input_tokens' => $role === 'assistant' ? fake()->numberBetween(100, 1000) : null,
            'output_tokens' => $role === 'assistant' ? fake()->numberBetween(50, 500) : null,
        ];
    }
}
