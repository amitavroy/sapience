<?php

declare(strict_types=1);

namespace App\Neuron\Persistence;

use App\Models\WorkflowInterrupt;
use NeuronAI\Exceptions\WorkflowException;
use NeuronAI\Workflow\Persistence\PersistenceInterface;
use NeuronAI\Workflow\WorkflowInterrupt as WorkflowInterruptObject;

use function serialize;
use function unserialize;

class DatabasePersistence implements PersistenceInterface
{
    public function __construct(
        protected string $model = WorkflowInterrupt::class
    ) {}

    public function save(string $workflowId, WorkflowInterruptObject $interrupt): void
    {
        $serializedData = serialize($interrupt);

        $this->model::updateOrCreate(
            ['workflow_id' => $workflowId],
            ['data' => $serializedData]
        );
    }

    public function load(string $workflowId): WorkflowInterruptObject
    {
        $model = $this->model::find($workflowId);

        if (! $model) {
            throw new WorkflowException("No saved workflow found for ID: {$workflowId}.");
        }

        return unserialize($model->data);
    }

    public function delete(string $workflowId): void
    {
        $this->model::destroy($workflowId);
    }
}
