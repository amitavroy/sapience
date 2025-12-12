<?php

namespace App\Models;

// use Illuminate\Contracts\Auth\MustVerifyEmail;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Notifications\Notifiable;
use Laravel\Fortify\TwoFactorAuthenticatable;

class User extends Authenticatable
{
    /** @use HasFactory<\Database\Factories\UserFactory> */
    use HasFactory, Notifiable, TwoFactorAuthenticatable;

    /**
     * The attributes that are mass assignable.
     *
     * @var list<string>
     */
    protected $fillable = [
        'name',
        'email',
        'password',
        'last_organisation_id',
    ];

    /**
     * The attributes that should be hidden for serialization.
     *
     * @var list<string>
     */
    protected $hidden = [
        'password',
        'two_factor_secret',
        'two_factor_recovery_codes',
        'remember_token',
    ];

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'email_verified_at' => 'datetime',
            'password' => 'hashed',
            'two_factor_confirmed_at' => 'datetime',
        ];
    }

    /**
     * Get the organisations that the user belongs to.
     */
    public function organisations(): BelongsToMany
    {
        return $this->belongsToMany(Organisation::class)
            ->withPivot('role')
            ->withTimestamps();
    }

    /**
     * Get the datasets owned by the user.
     */
    public function datasets(): HasMany
    {
        return $this->hasMany(Dataset::class, 'owner_id');
    }

    /**
     * Get the files uploaded by the user.
     */
    public function files(): HasMany
    {
        return $this->hasMany(File::class);
    }

    /**
     * Get the conversations started by the user.
     */
    public function conversations(): HasMany
    {
        return $this->hasMany(Conversation::class);
    }

    /**
     * Get the last organisation the user accessed.
     */
    public function lastOrganisation(): BelongsTo
    {
        return $this->belongsTo(Organisation::class, 'last_organisation_id');
    }

    /**
     * Check if the user is an admin of the given organisation.
     */
    public function isAdminOf(Organisation $organisation): bool
    {
        return $this->organisations()
            ->where('organisations.id', $organisation->id)
            ->wherePivot('role', 'admin')
            ->exists();
    }
}
