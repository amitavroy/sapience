<?php

namespace App\Console\Commands;

use App\Neuron\ResearchWorkflow;
use Illuminate\Console\Command;
use NeuronAI\Workflow\WorkflowState;

class ResearchTopic extends Command
{
    /**
     * The name and signature of the console command.
     *
     * @var string
     */
    protected $signature = 'app:research';

    /**
     * The console command description.
     *
     * @var string
     */
    protected $description = 'Command description';

    /**
     * Execute the console command.
     */
    public function handle()
    {
        // take input from user about the topic they want to research
        $topic = $this->ask('What is the topic you want to research?');

        $handler = ResearchWorkflow::make(
            state: new WorkflowState(['topic' => $topic])
        )->start();

        dump($handler->getResult());
    }
}
