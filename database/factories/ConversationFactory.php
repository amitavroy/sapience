<?php

namespace Database\Factories;

use App\Models\Dataset;
use App\Models\Organisation;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;
use Illuminate\Support\Str;

/**
 * @extends \Illuminate\Database\Eloquent\Factories\Factory<\App\Models\Conversation>
 */
class ConversationFactory extends Factory
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
            'title' => null,
            'user_id' => User::factory(),
            'organisation_id' => Organisation::factory(),
            'dataset_id' => Dataset::factory(),
        ];
    }
}
