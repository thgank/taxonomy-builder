"use client";

import { useActionState } from "react";

import { uploadDocumentsAction } from "@/features/upload-documents/actions/upload-documents-action";
import { initialActionState } from "@/shared/types/action-state";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";

export interface UploadDocumentsFormProps {
  collectionId: string;
}

export function UploadDocumentsForm({ collectionId }: UploadDocumentsFormProps) {
  const [state, action, isPending] = useActionState(
    uploadDocumentsAction.bind(null, collectionId),
    initialActionState,
  );

  return (
    <form action={action} className="space-y-4">
      <div>
        <Label htmlFor="document-upload">Upload documents</Label>
        <Input id="document-upload" multiple name="files" type="file" />
      </div>

      {state.message ? (
        <p
          className={
            state.status === "error"
              ? "text-sm text-[color:var(--color-ink)]"
              : "text-sm text-[color:var(--color-muted)]"
          }
        >
          {state.message}
        </p>
      ) : null}

      <Button disabled={isPending} type="submit" variant="secondary">
        {isPending ? "Uploading..." : "Upload documents"}
      </Button>
    </form>
  );
}
