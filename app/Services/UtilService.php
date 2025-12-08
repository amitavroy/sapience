<?php

namespace App\Services;

use App\Models\Dataset;
use App\Models\File;

class UtilService
{
    /**
     * Generate the S3 path for a file in a dataset.
     */
    public static function getFileS3Path(Dataset $dataset, File $file): string
    {
        return "datasets/{$dataset->id}/files/{$file->filename}";
    }
}
