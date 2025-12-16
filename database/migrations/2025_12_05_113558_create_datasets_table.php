<?php

use App\Models\Organisation;
use App\Models\User;
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('datasets', function (Blueprint $table) {
            $table->id();
            $table->uuid('uuid')->unique();
            $table->string('name');
            $table->text('description')->nullable();
            $table->text('instructions')->nullable();
            $table->text('output_instructions')->nullable();
            $table->boolean('is_active')->default(true);
            $table->foreignIdFor(User::class, 'owner_id');
            $table->foreignIdFor(Organisation::class);
            $table->timestamps();

            $table->foreign('owner_id')->references('id')->on('users');
            $table->foreign('organisation_id')->references('id')->on('organisations');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('datasets');
    }
};
