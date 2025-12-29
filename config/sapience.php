<?php

return [
    /**
     * Whether to use the fake workflow.
     * When using fake workflow, no actual AI service will be called.
     * Just basic logging will be done.
     * This is useful for development and testing.
     */
    'workflow_fake' => env('SAPIENCE_WORKFLOW_FAKE', false),
];
