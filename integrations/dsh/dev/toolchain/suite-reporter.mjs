/** Native Node test events, streamed without inventing success or coverage. */
export default async function* report(source) {
  yield `${JSON.stringify({schema_version:'C2pNodeRunMetadataV1',argv:process.argv,
    execArgv:process.execArgv,cwd:process.cwd(),node_version:process.version})}\n`;
  for await (const event of source) {
    if (['test:enqueue','test:dequeue','test:pass','test:fail','test:summary'].includes(event.type)) {
      const data=event.data;
      yield `${JSON.stringify({schema_version:'C2pNodeTestEventV1',type:event.type,
        file:data.file ?? null,line:data.line ?? null,column:data.column ?? null,
        name:data.name ?? null,nesting:data.nesting ?? null,testNumber:data.testNumber ?? null,
        skip:data.skip ?? false,todo:data.todo ?? false,
        details:data.details === undefined ? null : {type:data.details.type ?? null,
          passed:data.details.passed ?? null,errorType:data.details.error?.failureType ?? null},
        counts:data.counts ?? null})}\n`;
    }
  }
}
