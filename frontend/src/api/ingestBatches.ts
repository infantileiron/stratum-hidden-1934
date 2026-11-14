import {request} from './client';import type {IngestBatch} from '../types/entities';
export const list=()=>request<IngestBatch[]>('/ingest-batches');
export const detail=(id:string)=>request<IngestBatch>(`/ingest-batches/${id}`);
export const create=(data:unknown)=>request<IngestBatch>('/ingest-batches','POST',data);
export const sendFragment=(id:string,data:unknown)=>request<IngestBatch>(`/ingest-batches/${id}/fragments`,'POST',data);
export const seal=(id:string)=>request<IngestBatch>(`/ingest-batches/${id}/seal`,'POST');
export const publish=(id:string)=>request<IngestBatch>(`/ingest-batches/${id}/publish`,'POST');
