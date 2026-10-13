import api from "./api";
import { supabase } from "../lib/supabase";

type UploadInit = {
  dataset_id?: string;
  preparation_id?: string;
  storage_path: string;
};

export async function uploadCsvThroughStorage<T>(
  endpoint: "/api/datasets/upload" | "/api/data-preparation/analyze",
  file: File,
  onProgress: (progress: number) => void,
): Promise<T> {
  if (!supabase) {
    throw new Error("Supabase is not configured.");
  }
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.user) {
    throw new Error("You must be signed in to upload files.");
  }

  const initPath = endpoint === "/api/datasets/upload" ? "/api/datasets/upload/init" : "/api/data-preparation/upload/init";
  const completePath = endpoint === "/api/datasets/upload" ? "/api/datasets/upload/complete" : "/api/data-preparation/upload/complete";
  const cancelPath = endpoint === "/api/datasets/upload" ? "/api/datasets/upload/cancel" : "/api/data-preparation/upload/cancel";
  const { data: initialized } = await api.post<UploadInit>(initPath, {
    filename: file.name,
    content_type: file.type || "text/csv",
    file_size: file.size,
  });

  const documentId = initialized.dataset_id ?? initialized.preparation_id;
  if (!documentId) throw new Error("The upload session is missing its document ID.");
  const payload = endpoint === "/api/datasets/upload"
    ? { dataset_id: documentId }
    : { preparation_id: documentId };
  try {
    const pathSegments = initialized.storage_path.split("/");
    if (pathSegments.length < 3 || pathSegments[1] !== session.user.id) {
      throw new Error("The server returned an invalid storage location.");
    }

    onProgress(5);
    const { error: storageError } = await supabase.storage.from("datasets").upload(
      initialized.storage_path,
      file,
      { contentType: "text/csv", upsert: false },
    );
    if (storageError) throw storageError;
    onProgress(75);

    const { data } = await api.post<T>(completePath, payload);
    onProgress(100);
    return data;
  } catch (error) {
    await api.post(cancelPath, payload).catch(() => undefined);
    throw error;
  }
}
