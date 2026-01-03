<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class WorkflowInterrupt extends Model
{
    /**
     * The table associated with the model.
     *
     * @var string
     */
    protected $table = 'workflow_interrupts';

    /**
     * The primary key for the model.
     *
     * @var string
     */
    protected $primaryKey = 'workflow_id';

    /**
     * Indicates if the IDs are auto-incrementing.
     *
     * @var bool
     */
    public $incrementing = false;

    /**
     * The "type" of the primary key ID.
     *
     * @var string
     */
    protected $keyType = 'string';

    /**
     * The attributes that are mass assignable.
     *
     * @var list<string>
     */
    protected $fillable = [
        'workflow_id',
        'data',
    ];

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'data' => 'string',
        ];
    }
}
