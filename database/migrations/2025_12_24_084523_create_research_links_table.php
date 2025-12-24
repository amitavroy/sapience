<?php

use App\Models\Research;
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
        Schema::create('research_links', function (Blueprint $table) {
            $table->id();
            $table->foreignIdFor(Research::class)->index();
            $table->foreignIdFor(User::class)->index();
            $table->string('url');
            $table->longText('content')->nullable();
            $table->longText('summary')->nullable();
            $table->string('status')->default('pending');
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('research_links');
    }
};
