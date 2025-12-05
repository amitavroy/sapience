<?php

namespace Database\Factories;

use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;
use Illuminate\Support\Str;

/**
 * @extends \Illuminate\Database\Eloquent\Factories\Factory<\App\Models\File>
 */
class FileFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        $originalFilename = fake()->word().'.'.fake()->fileExtension();
        $filename = Str::random(40).'.'.fake()->fileExtension();

        return [
            'uuid' => (string) Str::uuid(),
            'original_filename' => $originalFilename,
            'filename' => $filename,
            'file_size' => fake()->numberBetween(1024, 10485760), // 1KB to 10MB
            'mime_type' => fake()->mimeType(),
            'user_id' => User::factory(),
        ];
    }
}
