import {useCallback,useEffect,useState} from 'react';
import {resourceEvents} from '../stores/resources';
export function useResource<T>(loader:()=>Promise<T>,initial:T){const [data,setData]=useState(initial),[error,setError]=useState(''),[loading,setLoading]=useState(true);
const reload=useCallback(()=>loader().then(v=>{setData(v);setError('')}).catch(e=>setError(e.message)).finally(()=>setLoading(false)),[loader]);
useEffect(()=>{let mounted=true;const load=()=>loader().then(v=>{if(mounted){setData(v);setError('')}}).catch(e=>mounted&&setError(e.message)).finally(()=>mounted&&setLoading(false));load();resourceEvents.addEventListener('refresh',load);const timer=setInterval(load,3000);return()=>{mounted=false;clearInterval(timer);resourceEvents.removeEventListener('refresh',load)}},[]);
return {data,error,loading,reload}}
