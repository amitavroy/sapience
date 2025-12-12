<?php

use App\Models\Dataset;
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
        Schema::create('conversations', function (Blueprint $table) {
            $table->id();
            $table->uuid('uuid')->unique();
            $table->string('title')->nullable();
            $table->foreignIdFor(User::class);
            $table->foreignIdFor(Organisation::class);
            $table->foreignIdFor(Dataset::class);
            $table->timestamps();

            $table->foreign('user_id')->references('id')->on('users');
            $table->foreign('organisation_id')->references('id')->on('organisations');
            $table->foreign('dataset_id')->references('id')->on('datasets');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('conversations');
    }
};
