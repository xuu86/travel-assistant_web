export type WorkspaceSnapshotRecord = {
  owner_id: string;
  feature_id: string;
  schema_version: number;
  updated_at: string;
  data: unknown;
};

export type GuestOwnerRecord = {
  key: "guest-owner-id";
  value: string;
};
