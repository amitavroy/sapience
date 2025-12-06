<?php

namespace Database\Seeders;

use App\Models\Organisation;
// use Illuminate\Database\Console\Seeds\WithoutModelEvents;
use App\Models\User;
use Illuminate\Database\Seeder;

class DatabaseSeeder extends Seeder
{
    /**
     * Seed the application's database.
     */
    public function run(): void
    {
        $user = User::firstOrCreate(
            ['email' => 'reachme@amitavroy.com'],
            [
                'name' => 'Amitav Roy',
                'password' => 'Password@123',
                'email_verified_at' => now(),
            ]
        );

        // Create an organisation and attach the user to it
        $organisation = Organisation::firstOrCreate([
            'name' => 'Devzone',
        ]);
        $organisation->users()->attach($user->id, ['role' => 'admin']);

        // Johon Doe user
        $johnDoe = User::firstOrCreate([
            'email' => 'john.doe@example.com',
            'name' => 'John Doe',
            'password' => 'Password@123',
            'email_verified_at' => now(),
        ]);

        // Create an organisation and attach the user to it
        $organisation2 = Organisation::firstOrCreate([
            'name' => 'Jhon Company',
        ]);
        $organisation2->users()->attach($johnDoe->id, ['role' => 'member']);

        // Add $user to $organisation2 as a member
        $organisation2->users()->attach($user->id, ['role' => 'member']);
    }
}
